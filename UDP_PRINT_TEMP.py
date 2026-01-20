import sys
import serial
import serial.tools.list_ports
from collections import deque
import socket

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QComboBox, QLabel, QMessageBox,
    QLineEdit, QCheckBox
)

from PySide6.QtCore import QThread, Signal, QTimer
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


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
        self.setWindowTitle("MCU Debug Console with Graph + UDP")
        self.setGeometry(200, 200, 800, 650)

        self.reader_thread = None
        self.raw_values = deque(maxlen=100)
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self.init_ui()
        self.refresh_ports()

        self.plot_timer = QTimer()
        self.plot_timer.timeout.connect(self.update_plot)
        self.plot_timer.start(100)

    def init_ui(self):
        layout = QVBoxLayout(self)

        # --- Port Selection Row ---
        port_row = QHBoxLayout()
        port_row.addWidget(QLabel("Serial Port:"))
        self.combo = QComboBox()
        port_row.addWidget(self.combo)
        self.refresh_button = QPushButton("🔄 Refresh")
        self.refresh_button.clicked.connect(self.refresh_ports)
        port_row.addWidget(self.refresh_button)
        layout.addLayout(port_row)

        # --- Connect/Disconnect Buttons ---
        btn_row = QHBoxLayout()
        self.connect_button = QPushButton("Connect")
        self.connect_button.clicked.connect(self.connect_serial)
        btn_row.addWidget(self.connect_button)
        self.disconnect_button = QPushButton("Disconnect")
        self.disconnect_button.clicked.connect(self.disconnect_serial)
        self.disconnect_button.setEnabled(False)
        btn_row.addWidget(self.disconnect_button)
        layout.addLayout(btn_row)

        # --- UDP Settings ---
        udp_row = QHBoxLayout()
        self.udp_enable = QCheckBox("Enable UDP")
        self.udp_enable.setChecked(False)
        udp_row.addWidget(self.udp_enable)
        udp_row.addWidget(QLabel("IP:"))
        self.udp_ip = QLineEdit("127.0.0.1")
        udp_row.addWidget(self.udp_ip)
        udp_row.addWidget(QLabel("Port:"))
        self.udp_port = QLineEdit("5005")
        udp_row.addWidget(self.udp_port)
        layout.addLayout(udp_row)

        # --- Serial Output Text Area ---
        self.text_box = QTextEdit()
        self.text_box.setReadOnly(True)
        layout.addWidget(self.text_box, stretch=2)

        # --- Plot Area ---
        self.figure = Figure(figsize=(5, 2))
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)
        self.line, = self.ax.plot([], [], 'g-')
        self.ax.set_ylim(0, 300)
        self.ax.set_xlim(0, 100)
        self.ax.set_title("Live Raw Values")
        self.ax.set_xlabel("Samples")
        self.ax.set_ylabel("Value")
        layout.addWidget(self.canvas, stretch=1)

    def refresh_ports(self):
        self.combo.clear()
        ports = serial.tools.list_ports.comports()
        for port in ports:
            self.combo.addItem(port.device)
        self.connect_button.setEnabled(True)

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

    def disconnect_serial(self):
        if self.reader_thread:
            self.reader_thread.stop()
            self.reader_thread = None
            self.text_box.append("Disconnected")

        self.connect_button.setEnabled(True)
        self.disconnect_button.setEnabled(False)

    def handle_disconnect(self, msg):
        self.text_box.append(msg)
        self.disconnect_serial()

    def update_output(self, text):
        self.text_box.append(text)

        # --- UDP Forwarding ---
        if self.udp_enable.isChecked():
            try:
                ip = self.udp_ip.text().strip()
                port = int(self.udp_port.text().strip())
                self.udp_socket.sendto(text.encode('utf-8'), (ip, port))
            except Exception as e:
                self.text_box.append(f"[UDP Error] {e}")

        # --- Parse for plotting ---
        if "raw value =" in text:
            try:
                value = int(text.split("=")[-1].strip())
                self.raw_values.append(value)
            except ValueError:
                pass

    def update_plot(self):
        y = list(self.raw_values)
        x = list(range(len(y)))
        self.line.set_data(x, y)
        self.ax.set_xlim(0, max(100, len(y)))
        self.canvas.draw()

    def closeEvent(self, event):
        self.disconnect_serial()
        self.udp_socket.close()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SerialMonitor()
    window.show()
    sys.exit(app.exec())
