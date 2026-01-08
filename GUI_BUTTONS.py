# GUI_BUTTONS.py BY Lorenzo Daidone - MIT

import sys
from PySide6.QtWidgets import QApplication, QWidget, QPushButton

# basic example of how to use the Pyside6 Qtmodule to create buttons to move around on the screen.
# Used as template for making GUI in lunix operatig systems which can be used as sensor nodes. 
# Main focus:
#
# - create widdget UI widget with buttons
# - have a OUTPUT when pressed

class MyWindow(QWidget):
    def __init__(self):
        super().__init__()

        # ---- Window setup ----
        self.setWindowTitle("Qt Geometry Learning")
        self.setFixedSize(600, 600)

        # ---- Button 1 ----
        self.btn1 = QPushButton("Button 1\npos=(20,20)\nsize=(120x50)", self)
        self.btn1.move(20, 20)          # x, y
        self.btn1.resize(120, 50)       # width, height
        self.btn1.clicked.connect(self.on_btn1)

        # ---- Button 2 ----
        self.btn2 = QPushButton("Button 2\npos=(200,20)\nsize=(150x60)", self)
        self.btn2.move(400, 20)
        self.btn2.resize(150, 60)
        self.btn2.clicked.connect(self.on_btn2)

        # ---- Button 3 ----
        self.btn3 = QPushButton("Button 3\npos=(100,120)\nsize=(180x80)", self)
        self.btn3.move(100, 120)
        self.btn3.resize(180, 80)
        self.btn3.clicked.connect(self.on_btn3)

    # ---- Button callbacks ----
    def on_btn1(self):
        print("Button 1 pressed")

    def on_btn2(self):
        print("Button 2 pressed")

    def on_btn3(self):
        print("Button 3 pressed")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MyWindow()
    window.show()
    sys.exit(app.exec())

