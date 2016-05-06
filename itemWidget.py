from PyQt5 import QtCore, QtGui
from PyQt5.QtWidgets import *

class ItemWidget(QWidget):
    """docstring for ItemWidget"""
    def __init__(self, parent = None):
        super(ItemWidget, self).__init__(parent)
        self.itemLayout = QHBoxLayout()

        self.fileCheckBox = QCheckBox()
        self.fileCheckBox.setObjectName("fileCheckBox")

        self.fileName = QLabel()
        self.fileName.setFixedWidth(180)

        self.state = QLabel()
        self.state.setFixedWidth(80)
        self.state.setObjectName("stateLabel")
        self.processBar = QProgressBar()

        self.itemLayout.addWidget(self.fileCheckBox)
        self.itemLayout.addWidget(self.fileName)
        self.itemLayout.addWidget(self.processBar)
        self.itemLayout.addWidget(self.state)

        self.setLayout(self.itemLayout)

        self.fileName.setStyleSheet('''color: rgb(0, 0, 255);''')
        self.state.setStyleSheet('''color: rgb(255, 0, 0);''')

    def setFileName(self, fileName = "None"):
        self.fileName.setText(fileName)

    def setState(self, state = "Queue"):
        self.state.setText(state)

    def setProcedure(self, percent):
        self.processBar.setProperty("value", percent)