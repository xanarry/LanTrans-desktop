from PyQt5 import QtCore, QtGui, QtWidgets
from threading import Thread
from PyQt5.QtWidgets import *
from itemWidget import ItemWidget
from mainUI import Ui_LanTrans
from os import path
import platform
import socket
import time
import sys
import traceback

########################UDP client and server##############################
class searchRecverThread(QtCore.QThread):
    updated = QtCore.pyqtSignal(str)
    """docstring for searchRecverThread"""
    def __init__(self, caller):
        super(searchRecverThread, self).__init__()
        self.caller = caller

    def run(self):
        '''"search udp server in LAN"'''
        self.udpClient = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udpClient.settimeout(self.caller.searchTimeout)
        self.udpClient.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        mes = socket.gethostname()
        buf = None
        address = None

        print("start broadcasting")
        self.updated.emit("<b><font color='blue'>MESSAGE:&nbsp;</font></b>Searching receiver")

        print(self.caller.searchTimes)
        for i in range(self.caller.searchTimes, -1, -1): #try trytimes to search
            try:
                self.udpClient.sendto(mes.encode(), ("<broadcast>", self.caller.UDPPort)) ##################send
                #self.udpClient.sendto(mes.encode(), ("127.0.0.1", 8888))
            except OSError as e:
                self.updated.emit("<b><font color='red'>ERROR:&nbsp;</font></b>" + str(e))
                traceback.print_exc(file=sys.stdout)
                self.caller.sendFileChecked()
                return

            try:
                buf, address = self.udpClient.recvfrom(self.caller.stringBufLen)################################################recv
                if address is not None and buf is not None:
                    break
            except socket.timeout as e:
                self.updated.emit("<b><font color='orange'>WARNING:&nbsp;</font></b>" + str(e) + ", try another " + str(i) + " times")
                print("timeout error, remain", i, "to try")
                traceback.print_exc(file=sys.stdout)

        if address is None:
            self.updated.emit("<b><font color='red'>ERROR:&nbsp;</font></b>Failed to find receiver, make sure it's online")
            print("failed to search server")
        else:
            self.updated.emit("<b><font color='green'>MESSAGE:&nbsp;</font></b>Find receiver: <b>" + str(address[0]) + "</b>&nbsp;&nbsp;<b><font color='red'>click start</font></b>")

            tempPort = int(buf.decode())
            self.caller.TCPPort = tempPort

            ld = list(address)
            ld[1] = tempPort
            address = tuple(ld)
            print("get server address:", address)
            self.updated.emit("<b><font color='green'>MESSAGE:&nbsp;</font></b>Server open port: <b>" + str(tempPort) +"</b>")


        self.udpClient.close()

        self.caller.receiverAddr = address
        self.caller.recoverState()

class waitSenderThread(QtCore.QThread):
    """docstring for waitSenderThread"""
    updated = QtCore.pyqtSignal(str)
    updateFile = QtCore.pyqtSignal(list)

    def __init__(self, caller):
        super(waitSenderThread, self).__init__()
        self.caller = caller
        self.port = caller.UDPPort;

    def run(self):
        '''"wait file sender"'''
        self.udpServer = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.udpServer.bind(("", self.port))
        except OSError as e:
            print("Address already in use")
            self.updated.emit("<b><font color='red'>ERROR:&nbsp;</font></b>" + str(e))
            traceback.print_exc(file=sys.stdout)
            self.caller.recoverState()
            return

        print("Waiting sender to send message")
        self.updated.emit("<b><font color='blue'>MESSAGE:&nbsp;</font></b>Waiting sender to send message")

        buf, address = self.udpServer.recvfrom(self.caller.stringBufLen)##############receive

        self.updated.emit("<b><font color='green'>MESSAGE:&nbsp;</font></b>Find sender: <b>" + address[0] + "</b>&nbsp;&nbsp;<b><font color='red'>going to accept</font></b>")
        print(buf.decode(), "from:", address)

        #return which port to sender
        serverOpenPort = str(self.caller.TCPPort)
        self.udpServer.sendto(serverOpenPort.encode(), address) ##################################send

        self.udpServer.close()

        self.caller.senderAddr = address
        self.caller.recoverState()

        self.caller.waitSenderToConnectThread.start()

########################TCP client and server##############################
class connectRecverThread(QtCore.QThread):
    """docstring for connectRecverThread"""
    updated = QtCore.pyqtSignal(str)
    def __init__(self, caller):
        super(connectRecverThread, self).__init__()
        self.caller = caller

    def run(self):
        self.tcpClient = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        print("Constructing TCP connection to receiver:", self.caller.receiverAddr)
        self.updated.emit("<b><font color='blue'>MESSAGE:&nbsp;</font></b>connection to receiver:" + str(self.caller.receiverAddr))

        for i in range(self.caller.connectTimes, -1, -1):
            try:
                #self.tcpClient.connect(("127.0.0.1", self.caller.TCPPort))
                self.tcpClient.connect(self.caller.receiverAddr)
                break
            except socket.error:
                self.updated.emit("<b><font color='red'>ERROR:&nbsp;</font></b>TCP connection failed, try another " + str(i) + " times")
                traceback.print_exc(file=sys.stdout)
                if i == 0:
                    return
                time.sleep(self.caller.connectTimeout)

        self.caller.TCPPort -= 1

        msg = ""
        for f in self.caller.files:
            msg += path.basename(f) + "~" + str(path.getsize(f)) + "|"

        self.tcpClient.sendall(msg.encode())

        msg = ""
        msg = self.tcpClient.recv(self.caller.stringBufLen)

        self.updated.emit("<b><font color='green'>MESSAGE:&nbsp;</font></b>connected successful")

        if len(msg.decode()):
            self.caller.hasConnectedToRecver = True
            self.caller.clientTcpConn = self.tcpClient


class waitSenderToConnectThread(QtCore.QThread):
    """docstring for waitSenderToConnectThread"""
    updated = QtCore.pyqtSignal(str)
    updateFileList = QtCore.pyqtSignal(list)

    def __init__(self, caller):
        super(waitSenderToConnectThread, self).__init__()
        self.caller = caller

    def run(self):
        self.tcpServer = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcpServer.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        #self.tcpServer.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)

        print("server port:", self.caller.TCPPort)
        self.tcpServer.bind(("", self.caller.TCPPort))

        print("Waiting to construct TCP conection with sender")
        self.updated.emit("<b><font color='blue'>MESSAGE:&nbsp;</font></b>Waiting sender connect, open port:<b>" + str(self.caller.TCPPort))

        self.tcpServer.listen(2) #listen client
        conn, senderAddr = self.tcpServer.accept() #create

        self.updated.emit("<b><font color='green'>MESSAGE:&nbsp;</font></b>Connected to sender: <b>" + str(senderAddr) + "</b>")
        print("Connected with send:", senderAddr)

        data = conn.recv(self.caller.stringBufLen)
        strmsg = data.decode()
        files = []
        for single in strmsg.split("|"):
            if len(single) > 0:
                fileName, length = single.split("~")
                files.append((fileName, length))

        self.caller.fileDesc = files;
        self.updateFileList.emit(files)

        self.updated.emit("<b><font color='blue'>MESSAGE:&nbsp;</font></b>Receiving files' description information")
        print("client is going to send:", data.decode())
        conn.sendall(data)

        self.caller.serverTcpConn = conn

        self.updated.emit("<b><font color='blue'>MESSAGE:&nbsp;</font></b>" + str(len(files)) + " files is going to send")

        if self.caller.serverTcpConn == None:
            self.updated.emit("<b><font color='red'>ERROR:&nbsp;</font></b>TCP connection failed")
            print("TCP connection failed")
        else: #start to receivfile
            self.caller.receiveFileThread.setFileDesc(self.caller.fileDesc, self.caller.savePath)
            self.caller.receiveFileThread.start()


########################TCP based file send and receive#################
class sendFileThread(QtCore.QThread):
    """docstring for sendFileThread"""
    updated = QtCore.pyqtSignal(str)
    updateRate = QtCore.pyqtSignal(tuple)
    def __init__(self, caller):
        super(sendFileThread, self).__init__()
        self.caller = caller

    def setFile(self, files):
        self.files = files
        print("set file")

    def run(self):
        '''send single file to receiver'''
        for i in range(len(self.files)):
            file = self.files[i]
            fileSize = path.getsize(file)

            print("sending:", file, "length:", fileSize)
            self.updated.emit("<b><font color='blue'>MESSAGE:&nbsp;</font></b><font color='blue'>Sending " + str(path.basename(file)) + "</font>")
            f = open(file, "rb")

            start = time.time()
            staticStart = start #used to calculate total time comsumpton
            cnt = 0
            hasSend = 0
            speed = 0

            strmsg = path.basename(file) + "~" + str(fileSize)

            #send what is going to send
            print("sender send ack")
            self.caller.clientTcpConn.sendall(strmsg.encode())
            #recv acknowledgement, actually this is used to sperate 2 files' bytes stream between two file
            self.caller.clientTcpConn.recv(2048)
            print("ack replyed, start")

            while True:
                content = f.read(8192)
                if not content:
                    break
                self.caller.clientTcpConn.sendall(content)
                end = time.time()

                cnt += len(content) #use to calculate speed
                hasSend += len(content) #used for rate

                if hasSend == fileSize: #finished send this file
                    self.updateRate.emit((i, 100, -1))
                    break

                self.updateRate.emit((i, int(hasSend / fileSize * 100), speed))

                if end - start >= 0.5:
                    speed = (cnt / 1024) / (end - start)
                    self.updateRate.emit((i, int(hasSend / fileSize * 100), speed))
                    #print("send finish:", hasSend, fileSize, int(hasSend / fileSize * 100), "speed", speed)
                    start = end
                    cnt = 0

            #receive acknowledgement message
            ack = self.caller.clientTcpConn.recv(2048)
            if int(ack.decode()) == fileSize:
                print("finish send:", file)
                timecomsumption = int((end - staticStart) * 10) / 10
                speed = (fileSize / 1024) / (end - staticStart)
                strspeed = ""
                if speed < 1024:
                    strspeed = str(int(speed * 100) / 100) + "KB/s"
                else:
                    strspeed = str(int(speed / 1024 * 100) / 100) + "MB/S"
                self.updated.emit("<b><font color='green'>MESSAGE:&nbsp;</font></b><font color='green'>Finish sending " + str(path.basename(file)) + "  time:" + str(timecomsumption) + "S  speed:" + strspeed + "</font>")

        self.caller.clientTcpConn.shutdown(socket.SHUT_RDWR)
        self.caller.clientTcpConn.close()
        self.updateRate.emit((-1, -1, -1))


class receiveFileThread(QtCore.QThread):
    """docstring for receiveFileThread"""
    updateRate = QtCore.pyqtSignal(tuple)
    updated = QtCore.pyqtSignal(str)
    def __init__(self, caller):
        super(receiveFileThread, self).__init__()
        self.caller = caller

    def setFileDesc(self, fileDesc, savepath):
        self.fileDesc = fileDesc
        self.savepath = savepath

    def run(self):
        '''receive file'''
        for i in range(len(self.fileDesc)):

            #receive current receiving file description
            msg = self.caller.serverTcpConn.recv(1024)
            #send acknowledgmet
            self.caller.serverTcpConn.sendall(msg)

            #get extract file information
            fileDesc = msg.decode().split("~") #like([file~length], []) first is valid
            print("receiving:", str(self.savepath) + "/" + str(fileDesc[0]), "length:", str(fileDesc[1]))
            self.updated.emit("<b><font color='blue'>MESSAGE:&nbsp;</font></b><font color='blue'>Receiving " + str(fileDesc[0]) + "</font>")

            #open file to save
            f = open(self.savepath + "/" + str(fileDesc[0]), "wb")

            #get numerical file size
            fileSize = int(str(fileDesc[1]))

            start = time.time()
            staticStart = start #used to calculate total time consumption

            cnt = 0
            hasRecv = 0
            speed = 0

            #start to receive file from internet
            while True:
                #read
                content = self.caller.serverTcpConn.recv(8192)
                if not content:
                    break
                #write
                f.write(content)
                end = time.time()

                cnt += len(content) #lenght to calculate speed
                hasRecv += len(content) #length to calculate rate

                #finish receive this file
                if hasRecv == fileSize:
                    self.updateRate.emit((i, 100, -1))
                    break

                self.updateRate.emit((i, int(hasRecv / fileSize * 100), speed))

                if end - start >= 0.5:
                    speed = (cnt / 1024) / (end - start)
                    #print("recv finish:", int(hasRecv / fileSize * 100), "speed:", speed, "size:", len(content))
                    self.updateRate.emit((i, int(hasRecv / fileSize * 100), speed))
                    start = end
                    cnt = 0

            if hasRecv == fileSize:
                ack = str(hasRecv)
                self.caller.serverTcpConn.sendall(ack.encode())

                print("finish receive:", self.fileDesc[0])
                timecomsumption = int((end - staticStart) * 10) / 10
                speed = (hasRecv / 1024) / (end - staticStart)
                strspeed = ""
                if speed < 1024:
                    strspeed = str(int(speed * 100) / 100) + "KB/s"
                else:
                    strspeed = str(int(speed / 1024 * 100) / 100) + "MB/S"

                self.updated.emit("<b><font color='green'>MESSAGE:&nbsp;</font></b><font color='green'>Finish receive  " + str(fileDesc[0]) + "  time:" + str(timecomsumption) + "S  speed:" + strspeed + "</font>")

        self.caller.serverTcpConn.shutdown(socket.SHUT_RDWR)
        self.caller.serverTcpConn.close()
        self.updateRate.emit((-1, -1, -1))
