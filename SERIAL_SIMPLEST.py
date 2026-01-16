import serial

ser = serial.Serial(
    port="/dev/cu.usbmodem111401",
    baudrate=115200,
    timeout=1
)
print("Connected")

while True:
    line = ser.readline().decode(errors="ignore").strip()
    if line:
        print(line)
