import socket
import threading
import random
import time
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)

# Game settings
TCP_PORT = 6000
UDP_PORT = 6001
SERVER_NAME = '0.0.0.0'
GUESS_RANGE = (1, 100)
MIN_PLAYERS = 2
MAX_PLAYERS = 4
GUESS_TIMEOUT = 10
GAME_DURATION = 60

# Global state
clients = {}  # name -> (tcp_socket, address)
udp_clients = {}  # name -> (udp_addr)
lock = threading.Lock()
secret_number = None
winner_announced = False
game_started = False

def broadcast_tcp(message):
    with lock:
        for name, (sock, _) in clients.items():
            try:
                sock.sendall(message.encode())
            except:
                logging.error(f"[ERROR] Failed to send TCP to {name}")

def handle_disconnection(username):
    with lock:
        logging.info(f"[DISCONNECT DETECTED] {username} has disconnected.")
        clients.pop(username, None)
        udp_clients.pop(username, None)
        broadcast_tcp(f"{username} has disconnected from the game!\n")

def prompt_remaining_player(sock, message, timeout=30):
    try:
        sock.sendall(f"[PROMPT]:{message}".encode())
        sock.settimeout(timeout)
        response = sock.recv(1024).decode().strip().lower()
        return response
    except:
        return None

def monitor_connection(username, conn):
    global game_started
    try:
        while True:
            conn.sendall(b"")
            time.sleep(2)
    except:
        handle_disconnection(username)
        with lock:
            if len(clients) == 1 and game_started:
                lone_player = next(iter(clients))
                sock, _ = clients[lone_player]
                response = prompt_remaining_player(sock, "You are the only one left. Do you want to continue? (yes/no)")
                if response != "yes":
                    broadcast_tcp("Game ended by the remaining player.\n")
                    game_started = False
                else:
                    broadcast_tcp(f"{lone_player} chose to continue alone.\n")
            elif len(clients) < MIN_PLAYERS:
                broadcast_tcp("Not enough players to continue. Ending game.\n")
                game_started = False

def handle_client(conn, addr):
    global clients, udp_clients, game_started

    try:
        conn.sendall("Welcome! Please join with 'JOIN <username>'\n".encode())
        data = conn.recv(1024).decode().strip()
        if not data.startswith("JOIN "):
            conn.sendall("Invalid command. Use 'JOIN <username>'\n".encode())
            conn.close()
            return

        username = data.split(" ", 1)[1]
        with lock:
            if username in clients:
                conn.sendall("Username already taken. Use another.\n".encode())
                conn.close()
                return
            clients[username] = (conn, addr)
            threading.Thread(target=monitor_connection, args=(username, conn), daemon=True).start()

        logging.info(f"[JOINED] {username} from {addr}")
        broadcast_tcp(f"{username} joined. Waiting for more players...\n")

        with lock:
            if len(clients) >= MIN_PLAYERS and not game_started:
                game_started = True
                threading.Thread(target=start_game, daemon=True).start()

        while True:
            time.sleep(1)

    except Exception as e:
        logging.error(f"[ERROR] Client handler error: {e}")

def start_game():
    global secret_number, winner_announced, udp_clients, game_started

    round_number = 1

    while True:
        with lock:
            if len(clients) < MIN_PLAYERS:
                broadcast_tcp("Not enough players to continue. Ending game.\n")
                logging.info("[GAME ENDED] Too few players.")
                game_started = False
                return

        logging.info(f"[ROUND {round_number}] Starting new round")
        secret_number = random.randint(*GUESS_RANGE)
        winner_announced = False

        broadcast_tcp(f"\n=== Round {round_number} ===")
        broadcast_tcp("Game started!")
        broadcast_tcp(f"Guess a number between {GUESS_RANGE[0]} and {GUESS_RANGE[1]}.\n")
        logging.info(f"[SECRET] Number is {secret_number}")

        guess_end_time = time.time() + GAME_DURATION
        while not winner_announced and time.time() < guess_end_time:
            time.sleep(1)

        if not winner_announced:
            broadcast_tcp("Time's up! No one guessed the number.\n")
        else:
            logging.info(f"[ROUND {round_number}] Winner announced.")

        udp_clients.clear()
        round_number += 1
        time.sleep(5)

def udp_listener():
    global winner_announced

    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_sock.bind((SERVER_NAME, UDP_PORT))
    logging.info(f"[UDP] Listening on {UDP_PORT}")

    while True:
        try:
            data, addr = udp_sock.recvfrom(1024)
            message = data.decode().strip()

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
            logging.error(f"[ERROR] UDP Listener: {e}")

def main():
    logging.info("[TCP] Starting TCP server...")
    tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_sock.bind((SERVER_NAME, TCP_PORT))
    tcp_sock.listen()

    logging.info(f"[READY] TCP on {TCP_PORT} | UDP on {UDP_PORT}")

    threading.Thread(target=udp_listener, daemon=True).start()

    while True:
        conn, addr = tcp_sock.accept()
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

if __name__ == "__main__":
    main()
