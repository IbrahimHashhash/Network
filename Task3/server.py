import socket
import threading
import random
import time
import collections

# Game settings
TCP_PORT = 6000
UDP_PORT = 6001
SERVER_NAME = '0.0.0.0'
MIN_PLAYERS = 2
MAX_PLAYERS = 4
GUESS_TIMEOUT = 10  # seconds to enter a guess
GAME_DURATION = 60  # seconds per round
GUESS_RANGE = (1, 100)

# Global state
clients = {}  # name -> (tcp_socket, address)
udp_clients = {}  # name -> (udp_addr)
player_last_guess_time = {}  # name -> timestamp of last guess
player_scores = collections.defaultdict(int)  # name -> score
lock = threading.Lock()
secret_number = None
winner_announced = False
game_started = False
current_round = 0


def broadcast_tcp(message):
    """Send a TCP message to all connected clients."""
    with lock:
        disconnected = []
        for name, (sock, _) in clients.items():
            try:
                sock.sendall(message.encode())
            except:
                print(f"[ERROR] Failed to send TCP to {name}")
                disconnected.append(name)
        
        # Clean up disconnected clients
        for name in disconnected:
            clients.pop(name, None)
            udp_clients.pop(name, None)
            player_last_guess_time.pop(name, None)


def monitor_connection(username, conn):
    """Continuously ping the TCP socket to detect disconnection immediately."""
    global game_started
    try:
        while True:
            try:
                conn.sendall(b"")  # attempt to send empty data
                time.sleep(2)  # ping every 2 seconds
            except:
                break
    except:
        pass
    
    # Handle disconnection
    with lock:
        if username in clients:
            print(f"[DISCONNECT DETECTED] {username} dropped connection.")
            clients.pop(username, None)
            udp_clients.pop(username, None)
            player_last_guess_time.pop(username, None)
            broadcast_tcp(f"**{username} has disconnected from the game.**\n")

            if len(clients) == 1 and game_started:
                lone_player = next(iter(clients))
                sock, _ = clients[lone_player]
                try:
                    sock.sendall(b"[PROMPT]:You are the only one left. Do you want to continue? (yes/no)")
                    sock.settimeout(30)
                    response = sock.recv(1024).decode().strip().lower()
                    if response != "yes":
                        broadcast_tcp("Game ended by the remaining player.\n")
                        game_started = False
                        return
                    else:
                        broadcast_tcp(f"{lone_player} chose to continue alone.\n")
                except:
                    broadcast_tcp("No response from the remaining player. Ending game.\n")
                    game_started = False
                    return
            elif len(clients) < MIN_PLAYERS:
                broadcast_tcp("Not enough players to continue. Ending game.\n")
                game_started = False
                return


def validate_player_name(name):
    """Validate that player name follows the required format."""
    # In a real implementation, this would check against the actual student names
    # For this example, we'll just check basic format
    return True  # Simplified for implementation


def handle_client(conn, addr):
    global clients, udp_clients, game_started

    try:
        conn.sendall("Welcome! Please join with 'JOIN <username>'\n".encode())
        data = conn.recv(1024).decode().strip()
        if not data.startswith("JOIN "):
            conn.sendall("Invalid command. Use 'JOIN <username>'\n".encode())
            conn.close()
            return

        username = data.split(" ")[1]
        
        # Validate player name format
        if not validate_player_name(username):
            conn.sendall("Invalid player name format. Please use lastName_firstName format.\n".encode())
            conn.close()
            return
            
        with lock:
            if username in clients:
                conn.sendall("Username already taken. Use another.\n".encode())
                conn.close()
                return
                
            # Check max players
            if len(clients) >= MAX_PLAYERS:
                conn.sendall(f"Game is full (max {MAX_PLAYERS} players). Try again later.\n".encode())
                conn.close()
                return
                
            clients[username] = (conn, addr)
            player_last_guess_time[username] = 0
            
        print(f"[JOINED] {username} from {addr}")
        broadcast_tcp(f"{username} joined. Waiting for more players...\n")

        # Start connection monitoring thread
        threading.Thread(target=monitor_connection, args=(username, conn), daemon=True).start()

        # Check if enough players to start
        with lock:
            if len(clients) >= MIN_PLAYERS and not game_started:
                game_started = True
                threading.Thread(target=start_game, daemon=True).start()

        # Keep client alive to detect disconnection properly
        while True:
            try:
                data = conn.recv(1024)
                if not data:
                    break
                # Process any additional TCP commands here
            except:
                break

    except Exception as e:
        print(f"[ERROR] Client handler error: {e}")
        
    finally:
        # Ensure cleanup when thread exits
        with lock:
            if username in clients:
                clients.pop(username, None)
                udp_clients.pop(username, None)
                player_last_guess_time.pop(username, None)


def start_game():
    global secret_number, winner_announced, udp_clients, game_started, current_round

    while True:
        with lock:
            if len(clients) < MIN_PLAYERS:
                broadcast_tcp("Not enough players to continue. Ending game.\n")
                print("[GAME ENDED] Too few players.")
                game_started = False
                return
                
        current_round += 1
        print(f"[ROUND {current_round}] Starting new round")
        secret_number = random.randint(*GUESS_RANGE)
        winner_announced = False
        
        # Reset guess timestamps for new round
        with lock:
            for name in clients:
                player_last_guess_time[name] = 0

        # Announce round start
        player_list = ", ".join(clients.keys())
        broadcast_tcp(f"\n=== Round {current_round} ===")
        broadcast_tcp(f"Game started with players: {player_list}")
        broadcast_tcp(f"Guess a number between {GUESS_RANGE[0]} and {GUESS_RANGE[1]}.\n")
        broadcast_tcp(f"You have {GUESS_TIMEOUT} seconds to make each guess and {GAME_DURATION} seconds total per round.\n")
        print(f"[SECRET] Number is {secret_number}")

        # 60-second guessing window
        round_end_time = time.time() + GAME_DURATION
        while not winner_announced and time.time() < round_end_time:
            time.sleep(1)
            remaining = int(round_end_time - time.time())
            
            # Broadcast time update every 10 seconds
            if remaining > 0 and remaining % 10 == 0:
                broadcast_tcp(f"{remaining} seconds remaining in this round.\n")

        if not winner_announced:
            broadcast_tcp(f"Time's up! No one guessed the number. The secret number was {secret_number}.\n")
            
        # Display scores after each round
        score_message = "Current scores:\n"
        with lock:
            for name, score in player_scores.items():
                if name in clients:  # Only show scores for connected players
                    score_message += f"- {name}: {score} points\n"
        broadcast_tcp(score_message)
        
        # Clear UDP client list for new round
        udp_clients.clear()
        time.sleep(5)  # Short break before next round


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

            # Check if player is registered and game is active
            with lock:
                if username not in clients or winner_announced or not game_started:
                    response = "Game not active or player not registered."
                    udp_sock.sendto(response.encode(), addr)
                    continue
                
                # Store UDP address for this client
                udp_clients[username] = addr
                
                # Check guess timeout
                current_time = time.time()
                if player_last_guess_time[username] > 0 and (current_time - player_last_guess_time[username]) < GUESS_TIMEOUT:
                    time_to_wait = GUESS_TIMEOUT - int(current_time - player_last_guess_time[username])
                    response = f"Too soon! Wait {time_to_wait} seconds before next guess."
                    udp_sock.sendto(response.encode(), addr)
                    continue
                    
                # Update last guess time
                player_last_guess_time[username] = current_time

            try:
                guess = int(guess_str)
                
                # Validate guess is in range
                if not (GUESS_RANGE[0] <= guess <= GUESS_RANGE[1]):
                    udp_sock.sendto("Out of bounds!".encode(), addr)
                    continue

                # Process the guess
                if guess < secret_number:
                    udp_sock.sendto("Higher".encode(), addr)
                elif guess > secret_number:
                    udp_sock.sendto("Lower".encode(), addr)
                else:
                    udp_sock.sendto("Correct!".encode(), addr)
                    
                    # Update scores and announce winner via TCP
                    with lock:
                        player_scores[username] += 1
                        winner_announced = True
                        broadcast_tcp(f"{username} guessed the number {secret_number} correctly and earned a point!\n")
                
            except ValueError:
                udp_sock.sendto("Invalid guess format. Please enter a number.".encode(), addr)

        except Exception as e:
            print(f"[ERROR] UDP Listener: {e}")


def main():
    print("[TCP] Starting server...")
    tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    tcp_sock.bind((SERVER_NAME, TCP_PORT))
    tcp_sock.listen(MAX_PLAYERS)

    print(f"[READY] TCP on {TCP_PORT} | UDP on {UDP_PORT}")
    print(f"[CONFIG] Min players: {MIN_PLAYERS}, Max players: {MAX_PLAYERS}")
    print(f"[CONFIG] Guess timeout: {GUESS_TIMEOUT}s, Game duration: {GAME_DURATION}s")

    # Start UDP listener thread
    threading.Thread(target=udp_listener, daemon=True).start()

    try:
        while True:
            conn, addr = tcp_sock.accept()
            threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()
    except KeyboardInterrupt:
        print("\n[SHUTDOWN] Server shutting down...")
    finally:
        tcp_sock.close()


if __name__ == "__main__":
    main()