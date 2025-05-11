import socket
import threading
import sys
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)

TCP_PORT = 6000
UDP_PORT = 6001

def receive_tcp_messages(sock, start_event):
    while True:
        try:
            data = sock.recv(1024)
            if not data:
                logging.info("[TCP] Server closed connection.")
                sys.exit(0)

            message = data.decode().strip()

            if "disconnected from the game" in message.lower():
                print("\n📣 " + message + "\n")
            else:
                logging.info(f"[SERVER]: {message}")

            if message.startswith("[PROMPT]:"):
                prompt_msg = message.split(":", 1)[1]
                response = input(prompt_msg + " ").strip().lower()
                sock.sendall(response.encode())
                continue

            if "Guess a number between" in message:
                start_event.set()

        except Exception as e:
            logging.error(f"[ERROR] TCP Listener: {e}")
            break
def timed_input(prompt, timeout=10):
    result = [None]

    def inner():
        result[0] = input(prompt)

    thread = threading.Thread(target=inner)
    thread.daemon = True
    thread.start()
    thread.join(timeout)

    if thread.is_alive():
        print(f"\n[WARNING] No input received in {timeout} seconds. Skipping guess.")
        return None
    return result[0]
def guessing_loop(udp_sock, server_ip, username, start_event):
    while True:
        start_event.wait()
        try:
            guess = timed_input("Your guess: ", timeout=10)
            if guess is None:
                continue  # skip this iteration
            if guess.lower() == 'exit':
                logging.info("[EXIT] Leaving game.")
                sys.exit(0)

            message = f"{username}:{guess}"
            udp_sock.sendto(message.encode(), (server_ip, UDP_PORT))
            udp_sock.settimeout(5)

            feedback, _ = udp_sock.recvfrom(1024)
            logging.info(f"[FEEDBACK]: {feedback.decode()}")

        except socket.timeout:
            logging.warning("[TIMEOUT] No response from server.")
        except Exception as e:
            logging.error(f"[ERROR] UDP Guessing: {e}")
            break

def main():
    server_ip = input("Enter TCP server IP (e.g., 127.0.0.1): ").strip()
    username = input("Enter your player name: ").strip()

    start_event = threading.Event()
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    try:
        tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_sock.connect((server_ip, TCP_PORT))
    except Exception as e:
        logging.error(f"[ERROR] Unable to connect to server: {e}")
        return

    try:
        welcome_msg = tcp_sock.recv(1024).decode()
        logging.info(welcome_msg)
        tcp_sock.sendall(f"JOIN {username}".encode())
    except Exception as e:
        logging.error(f"[ERROR] During initial TCP exchange: {e}")
        return

    threading.Thread(target=receive_tcp_messages, args=(tcp_sock, start_event), daemon=True).start()
    guessing_loop(udp_sock, server_ip, username, start_event)

if __name__ == "__main__":
    main()
