from PyQt5 import QtCore, QtGui, QtWidgets
from threading import Thread
from PyQt5.QtWidgets import *
from itemWidget import ItemWidget
from mainUI import Ui_LanTrans
from os import path
import getpass
import platform
import receiver
import sender

class LanTrans(Ui_LanTrans, QtWidgets.QMainWindow):
    def __init__(self):
        super(LanTrans, self).__init__()
        self.setupUi(self)

        self.DELIMITER = "    \neofeof    \neofeof"
        self.EOF = "    \neofeof"

        self.NAME_LEN_SPT = "~"
        self.FILES_SPT = "`"

        #udp
        self.UDPPort = 8888
        self.searchTimeout = 2
        self.searchTimes = 5

        #tcp
        self.TCPPort = 65500
        self.connectTimeout = 1
        self.connectTimes = 5

        #IO
        self.stringBufLen = 1024 * 8
        self.fileIOBufLen = 1024 * 64

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

        #添加信号槽, 更新当前状态
        #sender
        self.udpClientThread = sender.udpClientThread(caller = self)
        self.tcpClientThread = sender.tcpClientThread(caller = self)
        self.sendFileThread  = sender.sendFileThread(caller = self)
        self.udpClientThread.updateState.connect(self.updateState)
        self.tcpClientThread.updateState.connect(self.updateState)
        self.sendFileThread.updateState.connect(self.updateState)
        self.sendFileThread.updateRate.connect(self.updateProcess)
        
        #receiver
        self.udpServerThread   = receiver.udpServerThread(caller = self)
        self.tcpServerThread   = receiver.tcpServerThread(caller = self)
        self.receiveFileThread = receiver.receiveFileThread(caller = self)
        #state change update '''add update state slot'''
        self.udpServerThread.updateState.connect(self.updateState)
        self.tcpServerThread.updateState.connect(self.updateState)
        self.tcpServerThread.updateFileList.connect(self.genRecvList)
        self.receiveFileThread.updateState.connect(self.updateState)
        self.receiveFileThread.updateRate.connect(self.updateProcess)


        '''设置按钮监听'''
        self.removeBtn.clicked.connect(self.removeFileAction)
        self.savePathBtn.clicked.connect(self.savePathAction)
        self.addFileBtn.clicked.connect(self.addFileAction)
        self.sendFileRadio.clicked.connect(self.sendFileChecked)
        self.receiveFileRadio.clicked.connect(self.receiveFileChecked)
        self.connectHostBtn.clicked.connect(self.searchReceiverAction)
        self.startBtn.clicked.connect(self.startWork)

        '''将状态栏中的焦点移动到最后'''
        self.statusText.moveCursor(QtGui.QTextCursor.End)
        self.statusText.ensureCursorVisible()

        '''将列表焦点移动到最后'''
        self.statusText.moveCursor(QtGui.QTextCursor.End)
        self.statusText.ensureCursorVisible()

        #默认设置为发送文件
        self.sendFileChecked()

        self.actionExit.triggered.connect(QApplication.quit)
        self.actionAbout.triggered.connect(self.showAbout)

    def showAbout(self):
        QMessageBox.information(self, "关于此软件", "<b>LanTrans v_0.0.1</b><br>作者: Xanarry<br>Date:2016/5/4<br>E-mail:xanarry@163.com<br>boom! 安卓版正在开发中")

    def loadConfig(self):
        print("load configuration file")
        try:
            f = open("conf.ini", "r")
            for line in f:
                line = line.strip()
                if len(line) > 0 and line[0] != "#":
                    exec("self." + line)

        except FileNotFoundError as e:
            print("configure file not exist, using default")
            return

    def sendFileChecked(self):#=============================================================
        '''设置发送文件的面板状态'''
        if self.thisTimeFinished == True:
            self.reset()
            self.thisTimeFinished = False

        self.isSendFile = True
        self.receiveFileRadio.setEnabled(True)
        self.sendFileRadio.setEnabled(False)
        
        self.addFileBtn.setEnabled(True)
        self.removeBtn.setEnabled(True)
        self.connectHostBtn.setEnabled(True)
        self.startBtn.setVisible(True)
        self.startBtn.setDefault(True)
        self.startBtn.setEnabled(True)
        self.savePathBtn.setEnabled(False)

        self.connectHostBtn.setText("扫描")
        self.statusBar().showMessage("发送文件")

    def receiveFileChecked(self):#=====================================================================
        '''接收文件时设置的状态'''
        if self.thisTimeFinished == True:
            self.reset()##########################################################################################
            self.thisTimeFinished = False

        self.isSendFile = False
        self.sendFileRadio.setEnabled(True)
        self.receiveFileRadio.setEnabled(False)

        self.addFileBtn.setEnabled(False)
        self.removeBtn.setEnabled(False)
        self.savePathBtn.setEnabled(True)
        self.startBtn.setVisible(False)
        self.connectHostBtn.setEnabled(True)
        self.connectHostBtn.setDefault(True)

        self.connectHostBtn.setText("等待发送")
        self.statusBar().showMessage("接收文件")

    def disableAllBtn(self):
        '''禁掉所有按钮'''
        self.savePathBtn.setEnabled(False)
        self.addFileBtn.setEnabled(False)
        self.removeBtn.setEnabled(False)
        self.connectHostBtn.setEnabled(False)
        self.startBtn.setEnabled(False)
        self.sendFileRadio.setEnabled(False)
        self.receiveFileRadio.setEnabled(False)

    def disableList(self):
        '''禁掉列表中的选择按钮'''
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

        fileNames = QFileDialog.getOpenFileNames(self, "选择您想要传输的文件", self.baseDir)
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
            self.statusText.append("<b><font color='blue'>MESSAGE:&nbsp;</font></b>完成文件选择")


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
            self.thisTimeFinished = False

        self.savePath = QFileDialog.getExistingDirectory(None, "选择您的文件保存到何处", self.baseDir)
        if self.savePath is not None and len(self.savePath) > 1:
            self.statusText.append("<b><font color='blue'>MESSAGE:&nbsp;</font></b>文件将被保存到:" + str(self.savePath))
            print("receiver", "file will saved in:", self.savePath)

    def updateState(self, msg):
        if msg[0] == "warning":
            QMessageBox.information(self, "Warnning", msg[1])
            self.recoverState()
        else:
            self.statusText.append(msg[1])

    def updateProcess(self, pair):
        #(-1, -1, -1) all file finished
        if sum(pair) == -3:
            reply = QMessageBox.question(self, "Message", "任务完成, 是否继续?", QMessageBox.Yes, QMessageBox.No)
            if reply == QMessageBox.No:
                sys.exit()
            else:
                self.thisTimeFinished = True
                self.recoverState()
            return
        elif sum(pair) == -6:
            return

        itemWidget = self.fileList.itemWidget(self.fileList.item(pair[0]))#列表下标
        itemWidget.processBar.setProperty("value", pair[1])#对应条目的进度
        speed = None
        if pair[2] < 1024:#速度
            speed = str(int(pair[2] * 100) / 100) + "KB/s"
        elif pair[2] >= 0:
            speed = str(int(pair[2] / 1024 * 100) / 100) + "MB/S"
        if pair[2] == -1:
            speed = "已完成"

        itemWidget.state.setText(speed)

    def recoverState(self):
        if self.isSendFile == True:
            print("sender", "recoverState()", "this is send file client")
            self.sendFileChecked()
        elif self.isSendFile == False:
            print("receiver", "recoverState()", "this is receive file client")
            self.receiveFileChecked()

    def reset(self):
        self.files = []
        self.baseDir = "/home/" + getpass.getuser()
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
        self.disableAllBtn()
        self.disableList()
        if self.isSendFile == True:
            if len(self.files) == 0:
                QMessageBox.information(self, "Message", "请先选择文件")
                self.recoverState()
            else:
                self.startBtn.setEnabled(False)
                #clear file list
                self.udpClientThread.start()
        elif self.isSendFile == False:
            if self.savePath == None:
                QMessageBox.information(self, "Message", "请选择文件保存路径")
                self.recoverState()
            else:
                self.udpServerThread.start()

    def constructConnection(self):
        '''create a tcp connection'''
        if self.isSendFile == True:
            self.tcpClientThread.start()
            self.tcpClientThread.wait()
        elif self.isSendFile == False:
            if self.serverTcpConn == None:
                self.statusText.append("<b><font color='red'>ERROR:&nbsp;</font></b>TCP连接无效")
            else: #start to receivfile
                self.disableList()
                self.disableAllBtn()
                self.receiveFileThread.setFileDesc(self.fileDesc, self.savePath)
                self.receiveFileThread.start()

    #start button is only for send file
    def startWork(self):
        if len(self.files) == 0:
            QMessageBox.information(self, "Message", "请先选择文件")

        elif self.receiverAddr is not None:
            self.constructConnection()
            if self.hasConnectedToRecver == True:
                self.disableList()
                self.disableAllBtn()
                self.sendFileThread.setFile(self.files)
                self.sendFileThread.start()
        else:
            QMessageBox.information(self, "Message", "未建立有效连接, 请扫描局域网")

if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    w = LanTrans()
    w.loadConfig()
    w.sendFileChecked()
    w.show()
    sys.exit(app.exec_())
