"""A tiny HTTP proxy for tests: plain «GET http://…» and «CONNECT host:port». Counts what went through it."""
import select
import socket
import socketserver
import threading
import urllib.parse


class _Handler(socketserver.StreamRequestHandler):
    def handle(self):
        head = b""
        while b"\r\n\r\n" not in head:
            chunk = self.connection.recv(65536)
            if not chunk:
                return
            head += chunk
            if not head[:1].isalpha():           # SOCKS greeting etc. — a real HTTP proxy drops it too
                return
        line = head.split(b"\r\n", 1)[0].decode("latin-1")
        method, target, _ = line.split(" ", 2)
        self.server.seen.append(line)
        try:
            if method == "CONNECT":
                host, port = target.rsplit(":", 1)
                up = socket.create_connection((host, int(port)), timeout=10)
                self.connection.sendall(b"HTTP/1.1 200 Connection established\r\n\r\n")
                rest = head.split(b"\r\n\r\n", 1)[1]
                if rest:
                    up.sendall(rest)
            else:
                u = urllib.parse.urlsplit(target)
                up = socket.create_connection((u.hostname, u.port or 80), timeout=10)
                path = (u.path or "/") + (("?" + u.query) if u.query else "")
                up.sendall(head.replace(target.encode("latin-1"), path.encode("latin-1"), 1))
        except OSError:
            self.connection.sendall(b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\n\r\n")
            return
        socks = [self.connection, up]
        try:
            while True:
                r, _, _ = select.select(socks, [], [], 30)
                if not r:
                    break
                for s in r:
                    data = s.recv(65536)
                    if not data:
                        return
                    (up if s is self.connection else self.connection).sendall(data)
        except OSError:
            pass
        finally:
            up.close()


class MiniProxy(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self):
        super().__init__(("127.0.0.1", 0), _Handler)
        self.seen: list[str] = []
        self.port = self.server_address[1]
        threading.Thread(target=self.serve_forever, daemon=True).start()
