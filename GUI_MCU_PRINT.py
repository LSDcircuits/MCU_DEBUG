import sys
import serial
import serial.tools.list_ports

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QComboBox, QLabel, QMessageBox
)
from PySide6.QtCore import QThread, Signal


# ---------------- Serial Thread ----------------
class SerialReader(QThread):
    data_received = Signal(str)
    error = Signal(str)

    def __init__(self, port, baudrate=115200):
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self.running = True
        self.ser = None

    def run(self):
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
            while self.running:
                line = self.ser.readline().decode(errors="ignore").strip()
                if line:
                    self.data_received.emit(line)
        except Exception as e:
            self.error.emit(str(e))
        finally:
            if self.ser and self.ser.is_open:
                self.ser.close()

    def stop(self):
        self.running = False
        self.wait()


# ---------------- GUI ----------------
class SerialMonitor(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Simple MCU Serial Monitor")
        self.setFixedSize(600, 400)

        self.reader = None
        self.init_ui()
        self.refresh_ports()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # ---- Port row ----
        port_row = QHBoxLayout()
        port_row.addWidget(QLabel("Serial Port:"))

        self.port_combo = QComboBox()
        port_row.addWidget(self.port_combo)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh_ports)
        port_row.addWidget(self.refresh_btn)

        layout.addLayout(port_row)

        # ---- Connect buttons ----
        btn_row = QHBoxLayout()

        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self.connect_serial)
        btn_row.addWidget(self.connect_btn)

        self.disconnect_btn = QPushButton("Disconnect")
        self.disconnect_btn.clicked.connect(self.disconnect_serial)
        self.disconnect_btn.setEnabled(False)
        btn_row.addWidget(self.disconnect_btn)

        layout.addLayout(btn_row)

        # ---- Output ----
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output)

    # -------- Logic --------
    def refresh_ports(self):
        self.port_combo.clear()
        for p in serial.tools.list_ports.comports():
            self.port_combo.addItem(p.device)

    def connect_serial(self):
        if self.reader:
            return

        port = self.port_combo.currentText()
        if not port:
            QMessageBox.warning(self, "No port", "Select a serial port")
            return

        self.reader = SerialReader(port)
        self.reader.data_received.connect(self.output.append)
        self.reader.error.connect(self.on_error)
        self.reader.start()

        self.output.append(f"Connected to {port}")
        self.connect_btn.setEnabled(False)
        self.disconnect_btn.setEnabled(True)

    def disconnect_serial(self):
        if self.reader:
            self.reader.stop()
            self.reader = None
            self.output.append("Disconnected")

        self.connect_btn.setEnabled(True)
        self.disconnect_btn.setEnabled(False)

    def on_error(self, msg):
        self.output.append(f"[ERROR] {msg}")
        self.disconnect_serial()

    def closeEvent(self, event):
        self.disconnect_serial()
        event.accept()


# ---------------- Main ----------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = SerialMonitor()
    win.show()
    sys.exit(app.exec())