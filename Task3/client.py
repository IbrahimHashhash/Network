import socket
import threading
import sys
import time

# Game configuration
TCP_SERVER_IP = input("Enter server IP (e.g., 127.0.0.1): ").strip()
TCP_PORT = 6000
UDP_PORT = 6001

def receive_tcp_messages(tcp_socket):
    """Listens for messages from the server (TCP control messages)."""
    try:
        while True:
            msg = tcp_socket.recv(1024)
            if not msg:
                print("[TCP] Server closed the connection.")
                break
            print(f"[SERVER]: {msg.decode()}")
    except Exception as e:
        print(f"[ERROR] TCP receiving error: {e}")
    finally:
        tcp_socket.close()
        sys.exit()


def udp_guess_loop(username):
    """Sends guesses via UDP and receives feedback."""
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.settimeout(5)

    print("\n🕹️ Game started! Type your number guesses below.\n")

    while True:
        try:
            guess = input("Enter your guess (number): ").strip()
            if not guess.isdigit():
                print("⛔ Please enter a valid number.")
                continue

            msg = f"{username}:{guess}"
            udp_socket.sendto(msg.encode(), (TCP_SERVER_IP, UDP_PORT))

            # Wait for server feedback
            try:
                response, _ = udp_socket.recvfrom(1024)
                feedback = response.decode()
                print(f"[FEEDBACK]: {feedback}")

                if feedback == "Correct!":
                    print("🎉 You won the round!")
                    break

            except socket.timeout:
                print("⚠️ No response from server... try again.")

        except KeyboardInterrupt:
            print("\n[INFO] Exiting UDP guess mode.")
            break


def main():
    username = input("Enter your player name: ").strip()
    if not username:
        print("Username cannot be empty.")
        return

    # Establish TCP connection
    tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        tcp_socket.connect((TCP_SERVER_IP, TCP_PORT))
    except Exception as e:
        print(f"[ERROR] Could not connect to server: {e}")
        return

    threading.Thread(target=receive_tcp_messages, args=(tcp_socket,), daemon=True).start()

    # Join the game
    join_message = f"JOIN {username}"
    tcp_socket.sendall(join_message.encode())

    # Wait for game start
    while True:
        try:
            msg = tcp_socket.recv(1024).decode()
            print(f"[SERVER]: {msg}")

            if "Game started!" in msg:
                break
        except:
            print("[ERROR] Lost connection before game start.")
            return

    # Begin guessing using UDP
    udp_guess_loop(username)


if __name__ == "__main__":
    main()
