# GUI_TERMINAL_INPUT.py
import sys
from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QLabel
from PySide6.QtCore import QThread, Signal


class TerminalInputThread(QThread):
    text_received = Signal(str)

    def run(self):
        text = input("Enter something in terminal: ")
        self.text_received.emit(text)


class MyWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Terminal Input (Threaded)")
        self.setFixedSize(400, 200)

 
        self.btn = QPushButton("Get input from terminal", self)
        self.btn.move(20, 20)
        self.btn.resize(200, 40)
        self.btn.clicked.connect(self.on_button_pressed)


        self.label = QLabel("Waiting for input...", self)
        self.label.move(20, 80)
        self.label.resize(360, 40)

        self.input_thread = None

    def on_button_pressed(self):
        print("Button pressed → waiting for terminal input")
        self.label.setText("Check terminal and type input...")

        self.input_thread = TerminalInputThread()
        self.input_thread.text_received.connect(self.update_label)
        self.input_thread.start()

    def update_label(self, text):
        self.label.setText(f"Received: {text}")
        print(f"Received from terminal: {text}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MyWindow()
    window.show()
    sys.exit(app.exec())
