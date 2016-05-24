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

class udpClientThread(QtCore.QThread):
    updateState = QtCore.pyqtSignal(tuple)
    """此线程用于在局域网中发送广播信息, 通过接收者的返回信息得到接收者的IP地址"""
    def __init__(self, caller):
        super(udpClientThread, self).__init__()
        self.caller = caller

    def run(self):
        self.udpClient = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udpClient.settimeout(self.caller.searchTimeout)
        self.udpClient.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        msg = socket.gethostname()#向局域网中广播自己的主机名
        msg += self.caller.DELIMITER

        buf = None
        address = None

        print("sender", "start broadcasting")
        self.updateState.emit(("message", "<b><font color='blue'>MESSAGE:&nbsp;</font></b>正在扫描局域网中的接收者"))

        #广播多次信息代码设置的是5次, 每次隔2秒
        for i in range(self.caller.searchTimes, -1, -1): #try trytimes to search
            try:
                #广播信息
                self.udpClient.sendto(msg.encode("utf-8"), ("<broadcast>", self.caller.UDPPort)) ##################send
                #self.udpClient.sendto(msg.encode("utf-8"), ("127.0.0.1", 8888))
            except OSError as e:
                self.updateState.emit(("message", "<b><font color='red'>ERROR:&nbsp;</font></b>" + str(e)))
                traceback.print_exc(file=sys.stdout)
                self.caller.sendFileChecked()
                return

            try:
                #得到接收方的回复信息
                buf, address = self.udpClient.recvfrom(self.caller.stringBufLen)################################################recv
                if address is not None and buf is not None:
                    break
            except socket.timeout as e:
                self.updateState.emit(("message", "<b><font color='orange'>WARNING:&nbsp;</font></b>" + str(e) + "超时, 尝试剩下的" + str(i) + "次"))
                print("sender", "timeout error, remain", i, "to try")
                traceback.print_exc(file=sys.stdout)

        if address is None:
            self.updateState.emit(("message", "<b><font color='red'>ERROR:&nbsp;</font></b>无法在局域网中找到接受者, 检查对方是否在线"))
            print("failed to search server")
        else:
            self.updateState.emit(("message", "<b><font color='green'>MESSAGE:&nbsp;</font></b>找到接收者: <b>" + str(address[0]) + "</b>&nbsp;&nbsp;<b><font color='red'>点[开始]发送</font></b>"))

            #接收方将TCP使用的端口号发送过来
            tempPort = int(buf.decode("utf-8").strip())#将缓冲区的的端口号读成字符串在转化为整数
            self.caller.TCPPort = tempPort#将端口号保存到UI线程的全局变量中

            ld = list(address)
            ld[1] = tempPort
            address = tuple(ld)
            print("sender", "get server address:", address)
            self.updateState.emit(("message", "<b><font color='green'>MESSAGE:&nbsp;</font></b>接收端使用端口: <b>" + str(tempPort) +"</b>"))

        self.udpClient.close()

        self.caller.receiverAddr = address #将接收方的ip地址保存到UI线程的遍历中
        self.caller.recoverState() #恢复UI状态

class tcpClientThread(QtCore.QThread):
    """docstring for tcpClientThread"""
    updateState = QtCore.pyqtSignal(tuple)
    def __init__(self, caller):
        super(tcpClientThread, self).__init__()
        self.caller = caller

    def run(self):
        self.tcpClient = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        print("sender", "Constructing TCP connection to receiver:", self.caller.receiverAddr)#=========================================
        self.updateState.emit(("message", "<b><font color='blue'>MESSAGE:&nbsp;</font></b>正在连接到接收者:" + str(self.caller.receiverAddr)))

        for i in range(self.caller.connectTimes, -1, -1):
            try:
                #先接收方发起TCP连接
                self.tcpClient.connect(self.caller.receiverAddr)
                break
            except socket.error:
                self.updateState.emit(("message", "<b><font color='red'>ERROR:&nbsp;</font></b>TCP连接失败, 尝试剩下的" + str(i) + "次"))
                traceback.print_exc(file=sys.stdout)
                if i == 0:
                    return
                time.sleep(self.caller.connectTimeout)

        #使用过一次端口号之后要对其减一, 防止下次使用地址不可用
        self.caller.TCPPort -= 1

        #构建文件描述信息
        msg = ""
        for f in self.caller.files:
            msg += path.basename(f) + self.caller.NAME_LEN_SPT + str(path.getsize(f)) + self.caller.FILES_SPT

        msg += self.caller.DELIMITER
        #发送文件描述
        self.tcpClient.sendall(msg.encode("utf-8"))

        msg = ""
        #充值msg保存接收方(server)的回复信息
        msg = self.tcpClient.recv(self.caller.stringBufLen)

        self.updateState.emit(("message", "<b><font color='green'>MESSAGE:&nbsp;</font></b>成功建立连接"))

        if len(msg.decode("utf-8").strip()):#如果信息不为空, 说明server已经准备好接收文件了
            self.caller.hasConnectedToRecver = True
            self.caller.clientTcpConn = self.tcpClient #将次连接保存到UI, 等用户点start开始文件传输
            print("sender", "receiver is ready to receiv files")#======================================================

class sendFileThread(QtCore.QThread):
    """通过已经建立好的TCP连接, 读取本独文件通过IO流写入到网络"""
    updateState = QtCore.pyqtSignal(tuple)
    updateRate = QtCore.pyqtSignal(tuple)
    def __init__(self, caller):
        super(sendFileThread, self).__init__()
        self.caller = caller

    def setFile(self, files):
        self.files = files

    def run(self):
        '''send single file to receiver'''
        allFinished = True
        for i in range(len(self.files)): #发送列表中的每一个文件
            try:
                filepath = self.files[i]
                fileSize = path.getsize(filepath)

                print("sending:", filepath, "length:", fileSize)
                self.updateState.emit(("message", "<b><font color='blue'>MESSAGE:&nbsp;</font></b><font color='blue'>正在发送 " + str(path.basename(filepath)) + "</font>"))
                f = open(filepath, "rb")

                start = time.time()
                staticStart = start #used to calculate total time comsumpton
                cnt = hasSend = speed = 0

                #构建当前文件的文件描述
                strmsg = path.basename(filepath) + self.caller.NAME_LEN_SPT + str(fileSize) + self.caller.DELIMITER

                #send what is going to send
                print("sender", "send ack")
                self.caller.clientTcpConn.sendall(strmsg.encode("utf-8"))#发送文件描述
                #recv acknowledgement, actually this is used to sperate 2 files' bytes stream between two file
            
                fuck =  self.caller.clientTcpConn.recv(self.caller.stringBufLen)#接收文件描述
                print("reciver reply", fuck.decode("utf-8"))

                while True: #死循环开始文件传输
                    content = f.read(self.caller.fileIOBufLen)
                    if content is None: #如果文件传输完成, 或者异常发生
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
                ack = self.caller.clientTcpConn.recv(self.caller.stringBufLen)

                if int(ack.decode("utf-8").strip()) == fileSize:
                    timeDiff = end - staticStart
                    if timeDiff == 0.0:
                        timeDiff = 0.00001;

                    timecomsumption = int(timeDiff * 10) / 10
                    speed = (fileSize / 1024) / timeDiff
                    strspeed = ""
                    if speed < 1024:
                        strspeed = str(int(speed * 100) / 100) + "KB/s"
                    else:
                        strspeed = str(int(speed / 1024 * 100) / 100) + "MB/S"
                    self.updateState.emit(("message", "<b><font color='green'>MESSAGE:&nbsp;</font></b><font color='green'>完成发送:" + str(path.basename(filepath)) + "  耗时:" + str(timecomsumption) + "S  速度:" + strspeed + "</font>"))
                else:
                    print("sender", "Exception raised in transmition")
                    #delete file failed to transmit
            except Exception as e:
                self.updateState.emit(("warning", str(path.basename(filepath)) + "传输失败!\n网络中断或者对方已关闭程序"))
                print("receiver", "warning Network is not available or sender has closed!")
                traceback.print_exc(file=sys.stdout)
                allFinished = False
                break

        self.caller.clientTcpConn.shutdown(socket.SHUT_RDWR)
        self.caller.clientTcpConn.close()
        if allFinished == True:
            self.updateRate.emit((-1, -1, -1))
        else:
            self.updateRate.emit((-2, -2, -2))