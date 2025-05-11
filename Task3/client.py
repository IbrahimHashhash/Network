import socket
import threading
import sys

TCP_SERVER = input("Enter TCP server IP (e.g., 127.0.0.1): ")
TCP_PORT = 6000
UDP_PORT = 6001

start_event = threading.Event()
def tcp_listener(sock):
    while True:
        try:
            data = sock.recv(1024)
            if not data:
                print("[TCP] Server closed connection.")
                sys.exit(0)
            message = data.decode().strip()

            # 📣 Highlight disconnection messages
            if "disconnected from the game" in message.lower():
                print("\n📣 " + message + "\n")
            else:
                print("[SERVER]:", message)

            if message.startswith("[PROMPT]:"):
                prompt_msg = message.split(":", 1)[1]
                response = input(prompt_msg + " ").strip().lower()
                sock.sendall(response.encode())
                continue

            if "Guess a number between" in message:
                start_event.set()

        except Exception as e:
            print(f"[ERROR] TCP Listener: {e}")
            break


def udp_guessing(username):
    """Guessing loop triggered only after start_event is set."""
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    while True:
        start_event.wait()  # block until server signals game start
        try:
            guess = input("Your guess: ").strip()
            if guess.lower() == 'exit':
                print("[EXIT] Leaving game.")
                sys.exit(0)

            udp_sock.sendto(f"{username}:{guess}".encode(), (TCP_SERVER, UDP_PORT))
            udp_sock.settimeout(5)
            feedback, _ = udp_sock.recvfrom(1024)
            print("[FEEDBACK]:", feedback.decode())
        except socket.timeout:
            print("[TIMEOUT] No response from server.")
        except Exception as e:
            print(f"[ERROR] UDP Guessing: {e}")
            break

def main():
    username = input("Enter your player name: ").strip()

    tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        tcp_sock.connect((TCP_SERVER, TCP_PORT))
    except Exception as e:
        print(f"[ERROR] Unable to connect to server: {e}")
        return

    # Receive welcome and send JOIN
    print(tcp_sock.recv(1024).decode())
    tcp_sock.sendall(f"JOIN {username}".encode())

    threading.Thread(target=tcp_listener, args=(tcp_sock,), daemon=True).start()
    udp_guessing(username)

if __name__ == "__main__":
    main()
