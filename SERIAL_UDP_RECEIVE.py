import socket

# Configure the IP and port you want to receive data on
LISTEN_IP = "0.0.0.0"       # Listen on all interfaces
LISTEN_PORT = 5005          # Must match what you set in the GUI

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((LISTEN_IP, LISTEN_PORT))

print(f"Listening for UDP on {LISTEN_IP}:{LISTEN_PORT}...\n")

try:
    while True:
        data, addr = sock.recvfrom(1024)
        print(f"[{addr[0]}:{addr[1]}] → {data.decode('utf-8').strip()}")
except KeyboardInterrupt:
    print("\nStopped.")
    sock.close()
