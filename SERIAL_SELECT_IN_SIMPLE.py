import serial
import serial.tools.list_ports

# ---- List available ports ----
ports = list(serial.tools.list_ports.comports())

if not ports:
    print("No serial ports found")
    exit(1)

print("Available serial ports:")
for i, p in enumerate(ports):
    print(f"{i}: {p.device}")

# ---- Select port ----
idx = int(input("Select port number: "))
port = ports[idx].device

# ---- Open serial ----
ser = serial.Serial(port, 115200, timeout=1)
print(f"Connected to {port}")

# ---- Read loop ----
while True:
    line = ser.readline().decode(errors="ignore").strip()
    if line:
        print(line)

