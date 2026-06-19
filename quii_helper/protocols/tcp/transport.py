import socket


class TcpSocketTransport:
    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.sock: socket.socket | None = None

    def connect(self, timeout: float = 8.0) -> None:
        self.sock = socket.create_connection(
            (self.host, self.port), timeout=timeout
        )
        self.sock.settimeout(timeout)

    def close(self) -> None:
        if self.sock is None:
            return
        try:
            self.sock.close()
        finally:
            self.sock = None

    def send_all(self, packet: bytes) -> None:
        if self.sock is None:
            raise RuntimeError("socket is not connected")
        self.sock.sendall(packet)

    def recv_exact(self, size: int) -> bytes:
        if self.sock is None:
            raise RuntimeError("socket is not connected")
        chunks: list[bytes] = []
        remaining = size
        while remaining > 0:
            chunk = self.sock.recv(remaining)
            if not chunk:
                raise RuntimeError(f"socket closed while reading {size} bytes")
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)
