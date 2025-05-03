import socket
import threading
import random
import time

# Game settings
TCP_PORT = 6000
UDP_PORT = 6001
SERVER_NAME = '0.0.0.0'
MIN_PLAYERS = 2
MAX_PLAYERS = 4
GUESS_TIMEOUT = 10
GUESS_RANGE = (1, 100)

# Global state
clients = {}  # name -> (tcp_socket, address)
udp_clients = {}  # name -> (udp_addr)
lock = threading.Lock()
secret_number = None
winner_announced = False


def broadcast_tcp(message):
    """Send a TCP message to all connected clients."""
    with lock:
        for name, (sock, _) in clients.items():
            try:
                sock.sendall(message.encode())
            except:
                print(f"[ERROR] Failed to send TCP to {name}")


def handle_client(conn, addr):
    global clients, udp_clients

    try:
        conn.sendall("Welcome! Please join with 'JOIN <username>'\n".encode())
        data = conn.recv(1024).decode().strip()
        if not data.startswith("JOIN "):
            conn.sendall("Invalid command. Use 'JOIN <username>'\n".encode())
            conn.close()
            return

        username = data.split(" ")[1]
        with lock:
            if username in clients:
                conn.sendall("Username already taken. Use another.\n".encode())
                conn.close()
                return
            clients[username] = (conn, addr)

        print(f"[JOINED] {username} from {addr}")
        conn.sendall(f"Hello {username}! Waiting for other players...\n".encode())

        # Wait for game to start
        while len(clients) < MIN_PLAYERS:
            time.sleep(1)

        if len(clients) == MIN_PLAYERS:
            start_game()

    except Exception as e:
        print(f"[ERROR] Client handler: {e}")
    finally:
        with lock:
            if username in clients:
                clients.pop(username)
                udp_clients.pop(username, None)
                broadcast_tcp(f"{username} has disconnected.\n")
                print(f"[DISCONNECT] {username} removed.")


def start_game():
    global secret_number, winner_announced, udp_clients

    print("[GAME] Starting new game")
    secret_number = random.randint(*GUESS_RANGE)
    winner_announced = False

    broadcast_tcp(f"Game started! Guess a number between {GUESS_RANGE[0]} and {GUESS_RANGE[1]}.\n")
    print(f"[SECRET] Number is {secret_number}")

    # Allow 60 seconds of guessing
    guess_end_time = time.time() + 60
    while not winner_announced and time.time() < guess_end_time:
        time.sleep(1)
        # 🔍 Check if any clients disconnected
        disconnected = []
        with lock:
            for name, (sock, _) in clients.items():
                try:
                    sock.sendall(b"")  # ping to detect disconnection
                except:
                    disconnected.append(name)

            for name in disconnected:
                print(f"[DISCONNECT DETECTED] {name} has disconnected.")
                clients.pop(name, None)
                udp_clients.pop(name, None)
                broadcast_tcp(f"{name} has disconnected.\n")

        # ❌ End game early if not enough players
        with lock:
            if len(clients) < MIN_PLAYERS:
                broadcast_tcp("Not enough players remain. Ending game.\n")
                print("[GAME ENDED] Due to insufficient players.")
                return

    if not winner_announced:
        broadcast_tcp("Time's up! No one guessed the number.\n")
    else:
        print("[GAME] Game ended")

    # Cleanup for next round
    udp_clients.clear()


def udp_listener():
    global winner_announced

    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_sock.bind((SERVER_NAME, UDP_PORT))
    print(f"[UDP] Listening on {UDP_PORT}")

    while True:
        try:
            data, addr = udp_sock.recvfrom(1024)
            message = data.decode().strip()

            # Extract guess and username
            if ':' not in message:
                continue

            username, guess_str = message.split(':', 1)

            if username not in clients:
                continue

            if username not in udp_clients:
                udp_clients[username] = addr

            try:
                guess = int(guess_str)
                if not (GUESS_RANGE[0] <= guess <= GUESS_RANGE[1]):
                    udp_sock.sendto("Out of bounds!".encode(), addr)
                    continue

                if winner_announced:
                    udp_sock.sendto("Game already won.".encode(), addr)
                    continue

                if guess < secret_number:
                    udp_sock.sendto("Higher".encode(), addr)
                elif guess > secret_number:
                    udp_sock.sendto("Lower".encode(), addr)
                else:
                    udp_sock.sendto("Correct!".encode(), addr)
                    broadcast_tcp(f"{username} guessed the number {secret_number} correctly!\n")
                    winner_announced = True
            except ValueError:
                udp_sock.sendto("Invalid guess format.".encode(), addr)

        except Exception as e:
            print(f"[ERROR] UDP Listener: {e}")


def main():
    print("[TCP] Starting TCP server...")
    tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_sock.bind((SERVER_NAME, TCP_PORT))
    tcp_sock.listen()

    print(f"[READY] TCP on {TCP_PORT} | UDP on {UDP_PORT}")

    threading.Thread(target=udp_listener, daemon=True).start()

    while True:
        conn, addr = tcp_sock.accept()
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()


if __name__ == "__main__":
    main()
