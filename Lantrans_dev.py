from PyQt5 import QtCore, QtGui, QtWidgets
from threading import Thread
from PyQt5.QtWidgets import *
from itemWidget import ItemWidget
from mainUI import Ui_LanTrans
from os import path
import getpass
import platform
import Service

class LanTrans(Ui_LanTrans, QtWidgets.QMainWindow):
    def __init__(self):
        super(LanTrans, self).__init__()
        self.setupUi(self)

        #udp
        self.UDPPort = 8888
        self.searchTimeout = 2
        self.searchTimes = 5

        #tcp
        self.TCPPort = 65500
        self.connectTimeout = 1
        self.connectTimes = 5

        #IO
        self.stringBufLen = 2048
        self.fileIOBufLen = 8192

        #default open dir
        self.baseDir = "/home/" + getpass.getuser()
        #default files are going to send
        self.files = []

        self.senderAddr = None
        self.receiverAddr = None

        #socket connection for threading
        self.clientTcpConn = None
        self.serverTcpConn = None

        self.hasConnectedToRecver = False

        #default action is send file
        self.isSendFile = True
        #receive files' description
        self.fileDesc = []
        #where to save the receive file
        self.savePath = None

        #self.loadConfig()
        self.thisTimeFinished = False


        '''add services threads'''
        #udp
        self.searchRecverThread = Service.searchRecverThread(caller = self)
        self.waitSenderThread = Service.waitSenderThread(caller = self)
        #tcp
        self.connectRecverThread = Service.connectRecverThread(caller = self)
        self.waitSenderToConnectThread = Service.waitSenderToConnectThread(caller = self)
        self.sendFileThread = Service.sendFileThread(caller = self)
        self.receiveFileThread = Service.receiveFileThread(caller = self)

        '''add update state slot'''
        #state change update
        self.searchRecverThread.updated.connect(self.updateState)
        self.waitSenderThread.updated.connect(self.updateState)
        self.connectRecverThread.updated.connect(self.updateState)
        self.waitSenderToConnectThread.updated.connect(self.updateState)

        #files are going to receive list update
        self.waitSenderToConnectThread.updateFileList.connect(self.genRecvList)

        #transfer rate update
        self.sendFileThread.updateRate.connect(self.updateProcess)
        self.receiveFileThread.updateRate.connect(self.updateProcess)

        self.sendFileThread.updated.connect(self.updateState)
        self.receiveFileThread.updated.connect(self.updateState)

        '''set button action'''
        self.removeBtn.clicked.connect(self.removeFileAction)
        self.savePathBtn.clicked.connect(self.savePathAction)
        self.addFileBtn.clicked.connect(self.addFileAction)
        self.sendFileRadio.clicked.connect(self.sendFileChecked)
        self.receiveFileRadio.clicked.connect(self.receiveFileChecked)
        self.connectHostBtn.clicked.connect(self.searchReceiverAction)
        self.startBtn.clicked.connect(self.startWork)

        '''set stateText cursor auto move to end'''
        self.statusText.moveCursor(QtGui.QTextCursor.End)
        self.statusText.ensureCursorVisible()


        #set default action
        self.sendFileChecked()

        self.actionExit.triggered.connect(QApplication.quit)
        self.actionAbout.triggered.connect(self.showAbout)

    def showAbout(self):
        QMessageBox.information(self, "About this software", "<b>LanTrans v_0.0.1</b><br>Author: Xanarry<br>Date:2016-5-4<br>E-mail:xanarry@163.com<br>BOOM! Android edition is forth coming!")

    def loadConfig(self):
        try:
            f = open("conf.in", "r")
        except Exception:
            print("load config failed, using defalt config")
            return

    def sendFileChecked(self):
        if self.thisTimeFinished == True:
            self.reset()
            self.thisTimeFinished = False

        self.savePathBtn.setEnabled(False)
        self.addFileBtn.setEnabled(True)
        self.removeBtn.setEnabled(True)
        self.receiveFileRadio.setEnabled(True)
        self.isSendFile = True
        self.connectHostBtn.setText("Find receiver")
        self.connectHostBtn.setDefault(False)
        self.connectHostBtn.setEnabled(True)
        self.startBtn.setDefault(True)
        self.startBtn.setEnabled(True)
        self.startBtn.setVisible(True)

        self.statusBar().showMessage("you are going to send file")

    def receiveFileChecked(self):
        if self.thisTimeFinished == True:
            self.reset()
            self.recoverState()
            self.thisTimeFinished = False

        self.addFileBtn.setEnabled(False)
        self.removeBtn.setEnabled(False)
        self.savePathBtn.setEnabled(True)
        self.sendFileRadio.setEnabled(True)
        self.isSendFile = False
        self.startBtn.setVisible(False)

        self.connectHostBtn.setText("Ready to accept")
        self.connectHostBtn.setEnabled(True)
        self.connectHostBtn.setDefault(True)

        self.statusBar().showMessage("you are going to receive file")

    def disablePanel(self):
        '''when transmit all button should be disable'''
        self.savePathBtn.setEnabled(False)
        self.addFileBtn.setEnabled(False)
        self.removeBtn.setEnabled(False)
        self.connectHostBtn.setEnabled(False)

        for i in range(self.fileList.count()):
            itemWidget = self.fileList.itemWidget(self.fileList.item(i))
            itemWidget.fileCheckBox.setCheckState(2) #2 represent checked
            itemWidget.fileCheckBox.setEnabled(False)

    def addFileAction(self):
        '''promt a file selector window and add file to to sending file list'''
        if self.thisTimeFinished == True:
            self.reset()
            self.recoverState()
            self.thisTimeFinished = False

        fileNames = QFileDialog.getOpenFileNames(self, "Select File to transfer", self.baseDir)
        print(fileNames)

        for file in fileNames[0]:
            print(file)
            itemWidget = ItemWidget()
            itemWidget.setFileName(path.basename(file))
            self.files.append(file) #append new added file to ready list
            itemWidget.setState()
            itemWidget.setProcedure(0)
            fileItem = QListWidgetItem()
            fileItem.setSizeHint(itemWidget.sizeHint())
            self.fileList.addItem(fileItem)
            self.fileList.setItemWidget(fileItem, itemWidget)

        if len(self.files) > 0:
            self.statusText.append("<b><font color='blue'>MESSAGE:&nbsp;</font></b>Select files")


    def removeFileAction(self):
        #traverse from end to start
        if self.thisTimeFinished == True:
            self.reset()
            self.thisTimeFinished = False

        for i in range(self.fileList.count() - 1, -1, -1):
            itemWidget = self.fileList.itemWidget(self.fileList.item(i))
            if itemWidget.fileCheckBox.isChecked():
                self.fileList.takeItem(i)
                self.files.remove(self.files[i]) #remove file

    def savePathAction(self):
        '''choose where to save the file'''
        if self.thisTimeFinished == True:
            self.reset()##########################################################################################
            self.recoverState()
            self.thisTimeFinished = False

        self.savePath = QFileDialog.getExistingDirectory(None, "Select where to save your file", self.baseDir)
        if self.savePath is not None and len(self.savePath) > 1:
            self.statusText.append("<b><font color='blue'>MESSAGE:&nbsp;</font></b>Files will saved in:" + str(self.savePath))
            print("file will saved in:", self.savePath)

    def updateState(self, msg):
        self.statusText.append(msg)

    def updateProcess(self, pair):
        #(-1, -1, -1) all file finished
        if sum(pair) == -3:
            reply = QMessageBox.question(self, "Message", "All transmit has finished, click YES quit, or NO continue", QMessageBox.Yes, QMessageBox.No)
            if reply == QMessageBox.Yes:
                sys.exit()
            else:
                self.thisTimeFinished = True
            return


        itemWidget = self.fileList.itemWidget(self.fileList.item(pair[0]))
        itemWidget.processBar.setProperty("value", pair[1])
        speed = None
        if pair[2] < 1024:
            speed = str(int(pair[2] * 100) / 100) + "KB/s"
        elif pair[2] >= 0:
            speed = str(int(pair[2] / 1024 * 100) / 100) + "MB/S"
        if pair[2] == -1:
            speed = "finished"

        itemWidget.state.setText(speed)

    def recoverState(self):
        if self.isSendFile == True:
            print("this is send file client")
            self.sendFileChecked()
        elif self.isSendFile == False:
            print("this is receive file client")
            self.receiveFileChecked()

    def reset(self):
        self.files = []
        self.baseDir = "/home/" + getpass.getuser()
        self.fileDesc = []
        self.savePath = None
        self.senderAddr = None
        self.senderAddr = None
        self.receiverAddr = None
        self.receiverAddr = None
        self.clientTcpConn = None
        self.serverTcpConn = None
        self.hasConnectedToRecver = False
        self.statusText.setText("")
        self.fileList.clear()


    def genRecvList(self, files):
        for file in files:
            itemWidget = ItemWidget()
            itemWidget.setFileName(file[0])
            itemWidget.setState("queue")
            itemWidget.setProcedure(file[1])
            itemWidget.fileCheckBox.setCheckState(2) #2 represent checked
            itemWidget.fileCheckBox.setEnabled(False)

            fileItem = QListWidgetItem()
            fileItem.setSizeHint(itemWidget.sizeHint())

            self.fileList.addItem(fileItem)
            self.fileList.setItemWidget(fileItem, itemWidget)

    def searchReceiverAction(self):
        '''search file receiver in LAN'''
        self.addFileBtn.setEnabled(False)
        self.removeBtn.setEnabled(False)
        self.savePathBtn.setEnabled(False)
        self.sendFileRadio.setEnabled(True)
        self.receiveFileRadio.setEnabled(False)
        if self.isSendFile == True:
            print("send file")
            if len(self.files) == 0:
                QMessageBox.information(self, "Message", "Please select files first")
                self.recoverState()
            else:
                self.startBtn.setEnabled(False)
                self.searchRecverThread.start()
        elif self.isSendFile == False:
            if self.savePath == None:
                QMessageBox.information(self, "Message", "Please select where to save files")
                self.recoverState()
            else:
                self.waitSenderThread.start()

    def constructConnection(self):
        '''create a tcp connection'''
        if self.isSendFile == True:
            self.connectRecverThread.start()
            self.connectRecverThread.wait()
        elif self.isSendFile == False:
            if self.serverTcpConn == None:
                self.statusText.append("<b><font color='red'>ERROR:&nbsp;</font></b>no TCP connection constructed")
            else: #start to receivfile
                self.disablePanel()
                self.receiveFileThread.setFileDesc(self.fileDesc, self.savePath)
                self.receiveFileThread.start()

    #start button is only for send file
    def startWork(self):

        if len(self.files) == 0:
            QMessageBox.information(self, "Message", "Please select files first")

        elif self.receiverAddr != None:
            self.constructConnection()
            if self.hasConnectedToRecver == True:
                self.disablePanel()
                self.sendFileThread.setFile(self.files)
                self.sendFileThread.start()
        else:
            QMessageBox.information(self, "Message", "No connection constructed, Click search receiver")


if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    w = LanTrans()
    w.sendFileChecked()
    w.show()
    sys.exit(app.exec_())
