from socket import *

# Server configuration
PORT = 9910 
# Create a TCP socket
serverSocket = socket(AF_INET, SOCK_STREAM)
serverSocket.bind(("", PORT))
serverSocket.listen(1)  # Listen for 1 connection at a time
print(f"Server is running on 0.0.0.0:{PORT}...")  # Explicitly show 0.0.0.0 for clarity

# Main server loop
while True:
    # Accept client connection
    clientSocket, addr = serverSocket.accept()
    print(f"\n[Connected] {addr[0]}:{addr[1]}")
    
    try:
        # Receive data without immediate decoding
        request_data = clientSocket.recv(1024)
        if not request_data:
            clientSocket.close()
            continue

        # Try to decode safely - handle potential binary data
        try:
            request = request_data.decode('utf-8')
            print("[HTTP Request]\n" + request)
            
            # Parse the request line to get method and path
            request_line = request.split('\n')[0]
            parts = request_line.split()
            if len(parts) < 2:
                clientSocket.close()
                continue
            
            method, path = parts[0], parts[1]
            
            # Route to appropriate HTML files (now in html subfolder)
            if path == '/' or path == '/index.html' or path == '/main_en.html':
                filename = 'html/main_en.html'
            elif path == '/main_ar.html':
                filename = 'html/main_ar.html'
            elif path == '/mySite_1221140_en.html':
                filename = 'html/mySite_1221140_en.html'
            elif path == '/mySite_1221140_ar.html':
                filename = 'html/mySite_1221140_ar.html'
            # Handle search functionality
            elif path.startswith('/search'):
                # Extract query parameters
                query = path.split('?')[-1]
                params = {}
                for pair in query.split('&'):
                    if '=' in pair:
                        key, value = pair.split('=')
                        params[key] = value
                
                # Get filename and filetype from parameters
                filename = params.get('filename', '')
                filetype = params.get('type', 'imgs')  # Default to 'imgs' folder
                
                # Handle the new folder structure with subfolders
                if filetype == 'imgs':
                    file_path = f"{filetype}/material-pics/{filename}"  # Updated path with subfolder
                else:
                    file_path = f"{filetype}/{filename}"
                    
                try:
                    # Check if file exists locally
                    with open(file_path, 'rb'):
                        # If found, redirect to local file
                        redirect_path = '/' + file_path
                        response = (
                            "HTTP/1.1 302 Found\r\n"
                            f"Location: {redirect_path}\r\n"
                            "Connection: close\r\n\r\n"
                        )
                        print(f"[Redirect] 302 Found → {redirect_path}")
                except:
                    # If not found locally, redirect to Google search
                    google_type = 'isch' if filetype == 'imgs' else 'vid'  # 'isch' for images, 'vid' for videos
                    google_url = f"https://www.google.com/search?tbm={google_type}&q={filename}"
                    response = (
                        "HTTP/1.1 307 Temporary Redirect\r\n"
                        f"Location: {google_url}\r\n"
                        "Connection: close\r\n\r\n"
                    )
                    print(f"[Redirect] 307 Temporary Redirect → {google_url}")
                
                # Send redirect response and close connection
                clientSocket.sendall(response.encode())
                clientSocket.close()
                continue
            else:
                path_stripped = path.strip('/')
                if path_stripped.endswith('.html'):
                    filename = 'html/' + path_stripped
                else:
                    filename = path_stripped

            try:
                # Try to open and read the requested file
                with open(filename, 'rb') as f:
                    content = f.read()
                
                # Determine content type based on file extension
                if filename.endswith('.html'):
                    content_type = 'text/html'
                elif filename.endswith('.css'):
                    content_type = 'text/css'
                elif filename.endswith('.png'):
                    content_type = 'image/png'
                elif filename.endswith('.jpg') or filename.endswith('.jpeg'):
                    content_type = 'image/jpeg'
                elif filename.endswith('.mp4'):
                    content_type = 'video/mp4'
                else:
                    content_type = 'application/octet-stream'
                
                # Create and send HTTP response header
                header = (
                    "HTTP/1.1 200 OK\r\n"
                    f"Content-Type: {content_type}\r\n"
                    f"Content-Length: {len(content)}\r\n"
                    "Connection: close\r\n\r\n"
                ).encode()

                print(f"[Response] 200 OK for {addr[0]}:{addr[1]}")
                clientSocket.sendall(header + content)

            except FileNotFoundError:
                # Handle file not found error with a 404 response
                body = (
                    "<html><head><title>Error 404</title></head>"
                    "<body><h1 style='color:red;'>The file is not found</h1>"
                    f"<p>Client IP: {addr[0]}, Port: {addr[1]}</p>"
                    f"<p>Server Port: {PORT}</p></body></html>"
                ).encode()

                header = (
                    "HTTP/1.1 404 Not Found\r\n"
                    "Content-Type: text/html\r\n"
                    f"Content-Length: {len(body)}\r\n"
                    "Connection: close\r\n\r\n"
                ).encode()

                print(f"[Error] 404 Not Found for {addr[0]}:{addr[1]}")
                clientSocket.sendall(header + body)
                
        except UnicodeDecodeError:
            # Handle binary/non-UTF8 requests (could be browser favicon requests)
            print(f"[Info] Received binary or non-UTF8 data from {addr[0]}:{addr[1]}")
            # Send a generic response for non-HTTP requests
            response = (
                "HTTP/1.1 400 Bad Request\r\n"
                "Content-Type: text/plain\r\n"
                "Content-Length: 11\r\n"
                "Connection: close\r\n\r\n"
                "Bad Request"
            ).encode()
            clientSocket.sendall(response)

        # Close the connection
        clientSocket.close()

    except Exception as e:
        # Handle any other errors
        print(f"[Server Error] {e}")
        clientSocket.close()