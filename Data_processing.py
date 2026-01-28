import sys
import threading
import time
import socket
import serial

from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Signal, QObject


LISTEN_IP = "192.168.178.218"
LISTEN_PORT_YOLO = 5005
sockYOLO = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sockYOLO.bind((LISTEN_IP, LISTEN_PORT_YOLO))

PAPIprev = 0
DistanceList = []

ser = serial.Serial(port="/dev/cu.usbmodem11401", baudrate=115200, timeout=1)


class SystemState:
    def __init__(self):
        self.lock = threading.Lock()
        self.PAPI = 0
        self.distance = 0
        self.deldistance = 0
        self.lastdata = 0
        self.USstatus = "Initialising"
        self.running = True


class Bridge(QObject):
    update_signal = Signal(int, int, object, str)

bridge = Bridge()


class SensorYOLO(threading.Thread):
    def __init__(self, state):
        super().__init__(daemon=True)
        self.state = state

    def run(self):
        global PAPIprev
        while self.state.running:
            time.sleep(0.2)
            data, _ = sockYOLO.recvfrom(1024)
            PAPIraw = int(data.decode().strip())

            if PAPIraw == 5:
                self.state.PAPI = PAPIraw
            elif abs(PAPIraw - PAPIprev) <= 1:
                self.state.PAPI = PAPIraw
            elif abs(PAPIraw - PAPIprev) > 1:
                self.state.PAPI = 6
            else:
                self.state.PAPI = 7

            PAPIprev = PAPIraw


class SensorUS(threading.Thread):
    def __init__(self, state):
        super().__init__(daemon=True)
        self.state = state

    def run(self):
        while self.state.running:
            USraw = ser.readline().decode(errors="ignore").strip()
            if not USraw:
                continue

            parts = USraw.split(',')
            timeUS = int(parts[0])
            Ldata = self.state.lastdata

            if timeUS == 0:
                timepassed = time.time() - Ldata
                USstatus = "connection lost" if timepassed > 3 else "no data received yippie!!!"
            else:
                distanceUS = int(parts[1])
                self.state.lastdata = time.time()
                DistanceList.append(distanceUS)
                self.state.distance = distanceUS

                if len(DistanceList) > 1:
                    self.state.deldistance = DistanceList[-1] - DistanceList[-2]

                USstatus = "OK"

            self.state.USstatus = USstatus



class Monitor(threading.Thread):
    def __init__(self, state):
        super().__init__(daemon=True)
        self.state = state

    def run(self):
        while self.state.running:
            with self.state.lock:
                PAPI = self.state.PAPI
                distance = self.state.distance
                deldistance = self.state.deldistance
                USstatus = self.state.USstatus

            # Send data to GUI instead of print
            bridge.update_signal.emit(PAPI, distance, deldistance, USstatus)
            time.sleep(0.1)


class MonitorWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sensor Monitor")
        self.setFixedSize(400, 250)

        layout = QVBoxLayout()
        self.label = QLabel("Waiting for data...")
        layout.addWidget(self.label)
        self.setLayout(layout)

        bridge.update_signal.connect(self.update_display)

    def update_display(self, PAPI, distance, delta, status):
        self.label.setText(
            f"YOLO PAPI: {PAPI}\n"
            f"Distance: {distance}\n"
            f"Delta: {delta}\n"
            f"US Status: {status}"
        )


state = SystemState()

SensorYOLO(state).start()
SensorUS(state).start()
Monitor(state).start()


app = QApplication(sys.argv)
window = MonitorWindow()
window.show()

try:
    sys.exit(app.exec())
finally:
    state.running = False
