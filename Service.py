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

        mes = socket.gethostname()#向局域网中广播自己的主机名
        buf = None
        address = None

        print("start broadcasting")
        self.updated.emit("<b><font color='blue'>MESSAGE:&nbsp;</font></b>Searching receiver")

        #广播多次信息代码设置的是5次, 每次隔2秒
        for i in range(self.caller.searchTimes, -1, -1): #try trytimes to search
            try:
                #广播信息
                self.udpClient.sendto(mes.encode(), ("<broadcast>", self.caller.UDPPort)) ##################send
                #self.udpClient.sendto(mes.encode(), ("127.0.0.1", 8888))
            except OSError as e:
                self.updated.emit("<b><font color='red'>ERROR:&nbsp;</font></b>" + str(e))
                traceback.print_exc(file=sys.stdout)
                self.caller.sendFileChecked()
                return

            try:
                #得到接收方的回复信息
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

            #接收方将TCP使用的端口号发送过来
            tempPort = int(buf.decode())#将缓冲区的的端口号读成字符串在转化为整数
            self.caller.TCPPort = tempPort#将端口号保存到UI线程的变量中

            ld = list(address)
            ld[1] = tempPort
            address = tuple(ld)
            print("get server address:", address)
            self.updated.emit("<b><font color='green'>MESSAGE:&nbsp;</font></b>Server open port: <b>" + str(tempPort) +"</b>")


        self.udpClient.close()

        self.caller.receiverAddr = address #将接收方的ip地址保存到UI线程的遍历中
        self.caller.recoverState() #恢复UI状态

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

        #接收局域网中的信息
        buf, address = self.udpServer.recvfrom(self.caller.stringBufLen)##############receive

        self.updated.emit("<b><font color='green'>MESSAGE:&nbsp;</font></b>Find sender: <b>" + address[0] + "</b>&nbsp;&nbsp;<b><font color='red'>going to accept</font></b>")
        print(buf.decode(), "from:", address)

        #return which port to sender 将TCP使用的连接发送给文件发送方用于建立TCP连接
        serverOpenPort = str(self.caller.TCPPort)
        self.udpServer.sendto(serverOpenPort.encode(), address) ##################################send

        self.udpServer.close()

        self.caller.senderAddr = address #保存发送方的地址
        self.caller.recoverState()

        self.caller.waitSenderToConnectThread.start() #开启TCP服务端线程连接

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
                #先接收方发起TCP连接
                self.tcpClient.connect(self.caller.receiverAddr)
                break
            except socket.error:
                self.updated.emit("<b><font color='red'>ERROR:&nbsp;</font></b>TCP connection failed, try another " + str(i) + " times")
                traceback.print_exc(file=sys.stdout)
                if i == 0:
                    return
                time.sleep(self.caller.connectTimeout)

        #使用过一次端口号之后要对其减一, 防止下次使用地址不可用
        self.caller.TCPPort -= 1

        #构建文件描述信息
        msg = ""
        for f in self.caller.files:
            msg += path.basename(f) + "~" + str(path.getsize(f)) + "|"

        #发送文件描述
        self.tcpClient.sendall(msg.encode())

        msg = ""
        #充值msg保存接收方(server)的回复信息
        msg = self.tcpClient.recv(self.caller.stringBufLen)

        self.updated.emit("<b><font color='green'>MESSAGE:&nbsp;</font></b>connected successful")

        if len(msg.decode()):#如果信息不为空, 说明server已经准备好接收文件了
            self.caller.hasConnectedToRecver = True
            self.caller.clientTcpConn = self.tcpClient #将次连接保存到UI, 等用户点start开始文件传输


class waitSenderToConnectThread(QtCore.QThread):
    """docstring for waitSenderToConnectThread"""
    updated = QtCore.pyqtSignal(str)
    updateFileList = QtCore.pyqtSignal(list)

    def __init__(self, caller):
        super(waitSenderToConnectThread, self).__init__()
        self.caller = caller

    def run(self):
        #创建服务套接
        self.tcpServer = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcpServer.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        #绑定端口号
        print("server port:", self.caller.TCPPort)
        self.tcpServer.bind(("", self.caller.TCPPort))

        print("Waiting to construct TCP conection with sender")
        self.updated.emit("<b><font color='blue'>MESSAGE:&nbsp;</font></b>Waiting sender connect, open port:<b>" + str(self.caller.TCPPort))

        #监听连接
        self.tcpServer.listen(2) #listen client
        conn, senderAddr = self.tcpServer.accept() #create 建立连接

        self.updated.emit("<b><font color='green'>MESSAGE:&nbsp;</font></b>Connected to sender: <b>" + str(senderAddr) + "</b>")
        print("Connected with send:", senderAddr)

        data = conn.recv(self.caller.stringBufLen) #接收文件描述
        strmsg = data.decode()
        files = []
        for single in strmsg.split("|"): #解析出文件描述的内容信息
            if len(single) > 0:
                fileName, length = single.split("~")
                files.append((fileName, length))

        self.caller.fileDesc = files; #将结构化的文件描述保存到UI线程中
        self.updateFileList.emit(files)

        self.updated.emit("<b><font color='blue'>MESSAGE:&nbsp;</font></b>Receiving files' description information")
        print("client is going to send:", data.decode())
        conn.sendall(data)#发送接收文件的确认

        self.caller.serverTcpConn = conn #将此TCP连接保存到UI线程中

        self.updated.emit("<b><font color='blue'>MESSAGE:&nbsp;</font></b>" + str(len(files)) + " files is going to send")

        if self.caller.serverTcpConn == None:
            self.updated.emit("<b><font color='red'>ERROR:&nbsp;</font></b>TCP connection failed")
            print("TCP connection failed")
        else: #start to receivfile #调用传文件的线程开始传输
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
        for i in range(len(self.files)): #发送列表中的每一个文件
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

            #构建当前文件的文件描述
            strmsg = path.basename(file) + "~" + str(fileSize)

            #send what is going to send
            print("sender send ack")
            self.caller.clientTcpConn.sendall(strmsg.encode())#发送文件描述
            #recv acknowledgement, actually this is used to sperate 2 files' bytes stream between two file
            self.caller.clientTcpConn.recv(2048)#接收文件描述
            print("ack replyed, start")

            while True: #死循环开始文件传输
                content = f.read(8192)
                if not content: #如果文件传输完成, 或者异常发生
                    break
                self.caller.clientTcpConn.sendall(content)
                end = time.time()

                cnt += len(content) #use to calculate speed
                hasSend += len(content) #used for rate

                if hasSend == fileSize: #finished send this file #文件完成发送, 大小一致
                    self.updateRate.emit((i, 100, -1))
                    break

                self.updateRate.emit((i, int(hasSend / fileSize * 100), speed))

                if end - start >= 0.5: #每隔0.5秒更新一次速度
                    speed = (cnt / 1024) / (end - start)
                    self.updateRate.emit((i, int(hasSend / fileSize * 100), speed))
                    #print("send finish:", hasSend, fileSize, int(hasSend / fileSize * 100), "speed", speed)
                    start = end
                    cnt = 0

            #receive acknowledgement message #接收server的确认信息
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
