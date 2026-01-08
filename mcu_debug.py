import sys
import serial
import serial.tools.list_ports
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QComboBox, QLabel, QMessageBox
)
from PySide6.QtCore import QThread, Signal

#set myngoal to complete this code soon, for school and my self.
class SerialReader(QThread):
    data_received = Signal(str)
    disconnected = Signal(str)

    def __init__(self, port, baudrate=115200):
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self.serial = None
        self.running = True

    def run(self):
        try:
            self.serial = serial.Serial(self.port, self.baudrate, timeout=1)
            while self.running:
                line = self.serial.readline().decode("utf-8", errors="ignore").strip()
                if line:
                    self.data_received.emit(line)
        except Exception as e:
            self.disconnected.emit(f"Serial error: {e}")
        finally:
            if self.serial and self.serial.is_open:
                self.serial.close()

    def stop(self):
        self.running = False
        self.wait()


class SerialMonitor(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MCU Debug Console")
        self.setGeometry(200, 200, 650, 450)

        self.reader_thread = None
        self.init_ui()
        self.refresh_ports()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # ---- Port row ----
        port_row = QHBoxLayout()
        port_row.addWidget(QLabel("Serial Port:"))

        self.combo = QComboBox()
        port_row.addWidget(self.combo)

        self.refresh_button = QPushButton("🔄 Refresh")
        self.refresh_button.clicked.connect(self.refresh_ports)
        port_row.addWidget(self.refresh_button)

        layout.addLayout(port_row)

        # ---- Connect / Disconnect buttons ----
        btn_row = QHBoxLayout()

        self.connect_button = QPushButton("Connect")
        self.connect_button.clicked.connect(self.connect_serial)
        btn_row.addWidget(self.connect_button)

        self.disconnect_button = QPushButton("Disconnect")
        self.disconnect_button.clicked.connect(self.disconnect_serial)
        self.disconnect_button.setEnabled(False)
        btn_row.addWidget(self.disconnect_button)

        layout.addLayout(btn_row)

        # ---- Output box ----
        self.text_box = QTextEdit()
        self.text_box.setReadOnly(True)
        layout.addWidget(self.text_box)

    # ===== Refresh =====
    def refresh_ports(self):
        self.combo.clear()
        ports = serial.tools.list_ports.comports()
        for port in ports:
            self.combo.addItem(port.device)

        # Always allow connecting after refresh
        self.connect_button.setEnabled(True)

    # ===== Connect =====
    def connect_serial(self):
        if self.reader_thread:
            QMessageBox.information(self, "Already Connected", "Disconnect first.")
            return

        port = self.combo.currentText()
        if not port:
            QMessageBox.warning(self, "No Port Selected", "Choose a serial port.")
            return

        self.reader_thread = SerialReader(port)
        self.reader_thread.data_received.connect(self.update_output)
        self.reader_thread.disconnected.connect(self.handle_disconnect)
        self.reader_thread.start()

        self.connect_button.setEnabled(False)
        self.disconnect_button.setEnabled(True)

        self.text_box.append(f"Connected to {port}")

    # ===== Disconnect =====
    def disconnect_serial(self):
        if self.reader_thread:
            self.reader_thread.stop()
            self.reader_thread = None
            self.text_box.append("Disconnected")

        self.connect_button.setEnabled(True)
        self.disconnect_button.setEnabled(False)

    # ===== Auto‑disconnect handler =====
    def handle_disconnect(self, msg):
        self.text_box.append(msg)
        self.disconnect_serial()

    # ===== Append text safely =====
    def update_output(self, text):
        self.text_box.append(text)

    # ===== Cleanup on close =====
    def closeEvent(self, event):
        self.disconnect_serial()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SerialMonitor()
    window.show()
    sys.exit(app.exec())
