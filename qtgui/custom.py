#!/usr/bin/env python3

import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget
from PyQt5.uic import loadUi


class Window(QMainWindow):
    def __init__(self):
        super(Window, self).__init__()
        loadUi('qtgui.ui', self)
        
if __name__ == '__main__':
    app = QApplication(sys.argv)
    win = Window()
    win.show()
    sys.exit(app.exec())