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

class udpServerThread(QtCore.QThread):
    """docstring for udpServerThread"""
    updateState = QtCore.pyqtSignal(tuple)
    updateFile = QtCore.pyqtSignal(list)

    def __init__(self, caller):
        super(udpServerThread, self).__init__()
        self.caller = caller
        self.port = caller.UDPPort;

    def run(self):
        self.udpServer = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.udpServer.bind(("", self.port))
            print("receiver", "UDP port:", self.port)
        except OSError as e:
            print("receiver", "Address already in use")
            self.updateState.emit(("message", "<b><font color='red'>ERROR:&nbsp;</font></b>" + str(e)))
            traceback.print_exc(file=sys.stdout)
            self.caller.recoverState()
            return

        print("receiver", "Waiting sender to send message")
        self.updateState.emit(("message", "<b><font color='blue'>MESSAGE:&nbsp;</font></b>等待发送方广播信息"))

        #接收局域网中的信息
        buf, address = self.udpServer.recvfrom(self.caller.stringBufLen)##############receive

        print("receiver", "find sender at:", buf.decode("utf-8").strip(), "from:", address)
        self.updateState.emit(("message", "<b><font color='green'>MESSAGE:&nbsp;</font></b>找到发送者: <b>" + address[0] + "</b>&nbsp;&nbsp;<b><font color='red'>准备接收文件, 点[接收]</font></b>"))

        #return which port to sender 将TCP使用的连接发送给文件发送方用于建立TCP连接
        serverOpenPort = str(self.caller.TCPPort)
        self.udpServer.sendto(serverOpenPort.encode(), address) ##################################send

        self.udpServer.close()

        self.caller.senderAddr = address #保存发送方的地址
        self.caller.recoverState()

        self.caller.tcpServerThread.start() #开启TCP服务端线程连接接收文件

class tcpServerThread(QtCore.QThread):
    """docstring for tcpServerThread"""
    updateState = QtCore.pyqtSignal(tuple)
    updateFileList = QtCore.pyqtSignal(list)

    def __init__(self, caller):
        super(tcpServerThread, self).__init__()
        self.caller = caller

    def run(self):
        #创建服务套接
        self.tcpServer = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcpServer.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        #绑定端口号
        print("receiver", "server port:", self.caller.TCPPort)
        self.tcpServer.bind(("", self.caller.TCPPort))

        print("receiver", "Waiting to construct TCP conection with sender")
        self.updateState.emit(("message", "<b><font color='blue'>MESSAGE:&nbsp;</font></b>等待发送者建立连接, 端口:<b>" + str(self.caller.TCPPort)))

        #监听连接
        self.tcpServer.listen(1) #listen client
        conn, senderAddr = self.tcpServer.accept() #create 建立连接

        self.updateState.emit(("message", "<b><font color='green'>MESSAGE:&nbsp;</font></b>成功与: <b>" + str(senderAddr) + "建立连接</b>"))
        print("receiver", "Connected with sender, sender address:", senderAddr)

        data = conn.recv(self.caller.stringBufLen) #接收文件描述
        strmsg = data.decode("utf-8").strip()
        files = []
        for single in strmsg.split(self.caller.FILES_SPT): #解析出文件描述的内容信息
            if len(single) > 0:
                fileName, length = single.strip().split(self.caller.NAME_LEN_SPT)
                print(fileName, length)
                files.append((fileName, length))

        self.caller.fileDesc = files; #将结构化的文件描述保存到UI线程中
        self.updateFileList.emit(files)

        self.updateState.emit(("message", "<b><font color='blue'>MESSAGE:&nbsp;</font></b>接收文件描述信息"))
        print("receiver", "client is going to send:", data.decode("utf-8").strip())#=======================================================================
        self.updateState.emit(("message", "<b><font color='blue'>MESSAGE:&nbsp;</font></b>发送方有" + str(len(files)) + "个文件发送"))
       
        conn.sendall(data)#发送接收文件的确认

        self.caller.serverTcpConn = conn #将此TCP连接保存到UI线程中

        if self.caller.serverTcpConn == None:
            self.updateState.emit(("message", "<b><font color='red'>ERROR:&nbsp;</font></b>建立连接失败"))
            print("receiver", "TCP connection failed")
        else: #start to receivfile #调用传文件的线程开始传输
            self.caller.receiveFileThread.setFileDesc(self.caller.fileDesc, self.caller.savePath)
            self.caller.receiveFileThread.start()

class receiveFileThread(QtCore.QThread):
    """docstring for receiveFileThread"""
    updateRate = QtCore.pyqtSignal(tuple)
    updateState = QtCore.pyqtSignal(tuple)
    def __init__(self, caller):
        super(receiveFileThread, self).__init__()
        self.caller = caller

    def setFileDesc(self, fileDesc, savepath):
        self.fileDesc = fileDesc
        self.savepath = savepath
        print("receiver", "receiver Thread start, savepath:", savepath)#==============================

    def run(self):
        '''receive file'''
        allFinished = True
        for i in range(len(self.fileDesc)):#元组列表, 每个元组表示一个文件的文件名与大小
            try:
                #receive current receiving file description
                msg = self.caller.serverTcpConn.recv(self.caller.stringBufLen)
                #send acknowledgmet
                self.caller.serverTcpConn.sendall(msg)#直接将原信息返回

                #get extract file information
                fileDesc = msg.decode("utf-8").strip().split(self.caller.NAME_LEN_SPT) #like([file~length], []) first is valid
                print("receiving:", str(self.savepath) + "/" + str(fileDesc[0]), "length:", str(fileDesc[1]))
                self.updateState.emit(("message", "<b><font color='blue'>MESSAGE:&nbsp;</font></b><font color='blue'正在接收:" + str(fileDesc[0]) + "</font>"))

                #open file to save
                f = open(self.savepath + "/" + str(fileDesc[0]), "wb")

                #get numerical file size
                fileSize = int(str(fileDesc[1]))

                start = time.time()
                staticStart = start #used to calculate total time consumption

                cnt = hasRecv = speed = 0

                #start to receive file from internet
                while True:
                    #read
                    content = self.caller.serverTcpConn.recv(self.caller.fileIOBufLen)
                    if not content:
                        break
                    #write
                    f.write(content)
                    end = time.time()

                    cnt += len(content) #length to calculate speed
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

                    timeDiff = end - staticStart
                    if timeDiff == 0.0:
                        timeDiff = 0.00001

                    timecomsumption = int(timeDiff * 10) / 10
                    speed = (hasRecv / 1024) / timeDiff
                    strspeed = ""
                    if speed < 1024:
                        strspeed = str(int(speed * 100) / 100) + "KB/s"
                    else:
                        strspeed = str(int(speed / 1024 * 100) / 100) + "MB/S"

                    self.updateState.emit(("message", "<b><font color='green'>MESSAGE:&nbsp;</font></b><font color='green'>完成接收:" + str(self.fileDesc[0][0]) + "  耗时:" + str(timecomsumption) + "S  速度::" + strspeed + "</font>"))
                else:
                    print("receiver", "传输发生异常")

            except UnicodeDecodeError as e:
                self.updateState.emit(("warning", "信息编码错误"))
                allFinished = False
                break
            except Exception as e:
                self.updateState.emit(("warning", self.fileDesc[i][0] + "传输失败!\n网络中断或者对方已关闭程序"))
                os.remove(filepath + "/" + self.fileDesc[i][0]) #删除失败的文件
                self.updateState.emit(("message", "<b><font color='red'>ERROR:&nbsp;</font></b>传输发生异常</b>"))
                print("receiver", "warning Network is not available or sender has closed!")
                traceback.print_exc(file=sys.stdout)
                allFinished = False
                break

        self.caller.serverTcpConn.shutdown(socket.SHUT_RDWR)
        self.caller.serverTcpConn.close()
        if allFinished == True:
            self.updateRate.emit((-1, -1, -1))
        else:
            self.updateRate.emit((-2, -2, -2))