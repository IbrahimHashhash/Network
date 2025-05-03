from socket import *

HOST = 'localhost'
PORT = 9956  

serverSocket = socket(AF_INET, SOCK_STREAM)
serverSocket.bind((HOST, PORT))
serverSocket.listen(1)
print(f"Server is running on {HOST}:{PORT}...")

while True:
    clientSocket, addr = serverSocket.accept()
    print(f"\n[Connected] {addr[0]}:{addr[1]}")
    
    try:
        request = clientSocket.recv(1024).decode()
        if not request:
            clientSocket.close()
            continue

        print("[HTTP Request]\n" + request)

        request_line = request.split('\n')[0]
        parts = request_line.split()
        if len(parts) < 2:
            clientSocket.close()
            continue
        
        method, path = parts[0], parts[1]

        if path == '/' or path == '/index.html' or path == '/main_en.html':
            filename = 'main_en.html'
        elif path == '/main_ar.html':
            filename = 'main_ar.html'
        elif path == '/mySite_1221140_en.html':
            filename = 'mySite_1221140_en.html'
        elif path == '/mySite_1221140_ar.html':
            filename = 'mySite_1221140_ar.html'
        elif path.startswith('/search'):
            query = path.split('?')[-1]
            params = {}
            for pair in query.split('&'):
                if '=' in pair:
                    key, value = pair.split('=')
                    params[key] = value
            
            filename = params.get('filename', '')
            filetype = params.get('type', 'images')
            file_path = f"{filetype}/{filename}"
            try:
                with open(file_path, 'rb'):
                    redirect_path = '/' + file_path
                    response = (
                        "HTTP/1.1 302 Found\r\n"
                        f"Location: {redirect_path}\r\n"
                        "Connection: close\r\n\r\n"
                    )
                    print(f"[Redirect] 302 Found → {redirect_path}")
            except:
                google_type = 'isch' if filetype == 'images' else 'vid'
                google_url = f"https://www.google.com/search?tbm={google_type}&q={filename}"
                response = (
                    "HTTP/1.1 307 Temporary Redirect\r\n"
                    f"Location: {google_url}\r\n"
                    "Connection: close\r\n\r\n"
                )
                print(f"[Redirect] 307 Temporary Redirect → {google_url}")
            
            clientSocket.sendall(response.encode())
            clientSocket.close()
            continue
        else:
            filename = path.strip('/')

        try:
            with open(filename, 'rb') as f:
                content = f.read()
            
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
            
            header = (
                "HTTP/1.1 200 OK\r\n"
                f"Content-Type: {content_type}\r\n"
                f"Content-Length: {len(content)}\r\n"
                "Connection: close\r\n\r\n"
            ).encode()

            print(f"[Response] 200 OK for {addr[0]}:{addr[1]}")
            clientSocket.sendall(header + content)

        except FileNotFoundError:
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

        clientSocket.close()

    except Exception as e:
        print(f"[Server Error] {e}")
        clientSocket.close()
