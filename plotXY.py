# GUI_BUTTONS.py BY Lorenzo Daidone - MIT

import sys
from PySide6.QtWidgets import (
    QApplication, QWidget, QPushButton,
    QLineEdit, QLabel
)
from PySide6.QtCharts import QChart, QChartView, QScatterSeries
from PySide6.QtCore import Qt


class MyWindow(QWidget):
    def __init__(self):
        super().__init__()

        # ---- Window setup ----
        self.setWindowTitle("XY Plot Example")
        self.setFixedSize(600, 600)

        # ---- X input ----
        self.input_x = QLineEdit(self)
        self.input_x.setPlaceholderText("X value")
        self.input_x.move(20, 20)
        self.input_x.resize(100, 30)

        # ---- Y input ----
        self.input_y = QLineEdit(self)
        self.input_y.setPlaceholderText("Y value")
        self.input_y.move(140, 20)
        self.input_y.resize(100, 30)

        # ---- Button ----
        self.btn1 = QPushButton("Plot", self)
        self.btn1.move(260, 20)
        self.btn1.resize(100, 30)
        self.btn1.clicked.connect(self.on_btn1)

        # ---- Status label ----
        self.output_label = QLabel("Enter X and Y, then press Plot", self)
        self.output_label.move(20, 60)
        self.output_label.resize(340, 30)

        # ---- Plot setup ----
        self.series = QScatterSeries()
        self.series.setMarkerSize(10.0)

        self.chart = QChart()
        self.chart.addSeries(self.series)
        self.chart.createDefaultAxes()
        self.chart.setTitle("XY Plot")

        self.chart_view = QChartView(self.chart, self)
        self.chart_view.setRenderHint(self.chart_view.renderHints())
        self.chart_view.move(20, 100)
        self.chart_view.resize(560, 480)

    # ---- Button callback ----
    def on_btn1(self):
        try:
            x = float(self.input_x.text())
            y = float(self.input_y.text())

            self.series.append(x, y)
            self.output_label.setText(f"Plotted point: ({x}, {y})")
            print(f"Plotted: x={x}, y={y}")

        except ValueError:
            self.output_label.setText("Invalid input (enter numbers)")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MyWindow()
    window.show()
    sys.exit(app.exec())
