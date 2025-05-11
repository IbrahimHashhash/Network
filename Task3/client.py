import socket
import threading
import sys
import time

# Game settings
TCP_PORT = 6000
UDP_PORT = 6001
GUESS_TIMEOUT = 10  # seconds

# Ask for server IP or use localhost
TCP_SERVER = input("Enter TCP server IP (e.g., 127.0.0.1): ")
if not TCP_SERVER:
    TCP_SERVER = "127.0.0.1"

# Game state
game_active = False
start_event = threading.Event()
last_guess_time = 0

def tcp_listener(sock):
    """Listen for TCP messages from the server."""
    global game_active
    
    while True:
        try:
            data = sock.recv(1024)
            if not data:
                print("\n[DISCONNECT] Server closed connection.")
                sys.exit(0)
                
            message = data.decode().strip()

            # Highlight important messages
            if "disconnected from the game" in message.lower():
                print("\n📣 " + message + "\n")
            elif "winner" in message.lower() or "correctly" in message.lower():
                print("\n🏆 " + message + "\n")
            elif "=== Round" in message:
                print("\n" + "="*50)
                print(message)
                print("="*50)
                game_active = True
            else:
                print("[SERVER]:", message)

            # Handle server prompts
            if message.startswith("[PROMPT]:"):
                prompt_msg = message.split(":", 1)[1]
                response = input(prompt_msg + " ").strip().lower()
                sock.sendall(response.encode())
                continue

            # Set game active state based on messages
            if "Guess a number between" in message:
                game_active = True
                start_event.set()
            elif "Time's up" in message or "Game ended" in message:
                game_active = False
                start_event.clear()

        except Exception as e:
            print(f"[ERROR] TCP Listener: {e}")
            break
    
    print("[DISCONNECT] Lost connection to server.")
    sys.exit(1)


def udp_guessing(username):
    """Handle the UDP guessing logic with timeout."""
    global last_guess_time
    
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    while True:
        # Wait until server signals game start
        start_event.wait()
        
        # Check if we can make a guess yet
        current_time = time.time()
        time_since_last = current_time - last_guess_time
        
        if time_since_last < GUESS_TIMEOUT and last_guess_time > 0:
            time_to_wait = GUESS_TIMEOUT - int(time_since_last)
            print(f"[WAIT] Please wait {time_to_wait} seconds before your next guess.")
            time.sleep(min(1, time_to_wait))  # Sleep but check for game state changes
            continue
            
        if not game_active:
            time.sleep(1)  # Don't burn CPU if game is not active
            continue
            
        try:
            guess = input("\nYour guess (or 'exit' to quit): ").strip()
            
            if not guess:
                continue
                
            if guess.lower() == 'exit':
                print("[EXIT] Leaving game.")
                sys.exit(0)
                
            # Try to validate input is a number
            try:
                int(guess)
            except ValueError:
                print("[ERROR] Please enter a valid number.")
                continue
                
            # Record guess time and send to server
            last_guess_time = time.time()
            udp_sock.sendto(f"{username}:{guess}".encode(), (TCP_SERVER, UDP_PORT))
            
            # Wait for server response
            try:
                udp_sock.settimeout(5)
                feedback, _ = udp_sock.recvfrom(1024)
                feedback_msg = feedback.decode().strip()
                
                # Format feedback based on content
                if feedback_msg == "Higher":
                    print("📈 [FEEDBACK]: Higher! Try a larger number.")
                elif feedback_msg == "Lower":
                    print("📉 [FEEDBACK]: Lower! Try a smaller number.")
                elif feedback_msg == "Correct!":
                    print("🎉 [FEEDBACK]: Correct! You got it!")
                elif "bounds" in feedback_msg.lower():
                    print("⚠️ [ERROR]: Your guess is out of the valid range!")
                    last_guess_time = 0  # Allow immediate retry for out of bounds
                elif "too soon" in feedback_msg.lower():
                    print(f"⏱️ [TIMEOUT]: {feedback_msg}")
                else:
                    print(f"[FEEDBACK]: {feedback_msg}")
                
            except socket.timeout:
                print("[TIMEOUT] No response from server.")
            
        except Exception as e:
            print(f"[ERROR] UDP Guessing: {e}")
            time.sleep(1)


def main():
    """Main client function handling connection and setup."""
    
    print("="*50)
    print("Welcome to the Number Guessing Game!")
    print("="*50)
    
    # Get username with validation
    while True:
        username = input("Enter your player name: ").strip()
        if not username:
            print("Username cannot be empty.")
            continue
        if len(username) < 3:
            print("Username must be at least 3 characters.")
            continue
        break
    
    print(f"Connecting to server at {TCP_SERVER}:{TCP_PORT}...")
    
    # Set up TCP socket
    tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        tcp_sock.connect((TCP_SERVER, TCP_PORT))
    except Exception as e:
        print(f"[ERROR] Unable to connect to server: {e}")
        return

    # Handle welcome message and join
    welcome = tcp_sock.recv(1024).decode()
    print(welcome)
    
    # Send JOIN command
    tcp_sock.sendall(f"JOIN {username}".encode())
    
    # Start listener threads
    tcp_thread = threading.Thread(target=tcp_listener, args=(tcp_sock,), daemon=True)
    tcp_thread.start()
    
    # Start UDP guessing thread
    udp_thread = threading.Thread(target=udp_guessing, args=(username,), daemon=True)
    udp_thread.start()
    
    # Keep main thread alive
    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n[EXIT] Closing connection...")
    finally:
        try:
            tcp_sock.close()
        except:
            pass


if __name__ == "__main__":
    main()