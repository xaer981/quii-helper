import socket
import time


class TcpSocketTransport:
    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.sock: socket.socket | None = None
        self._receive_buffer = bytearray()

    def connect(self, timeout: float = 8.0) -> None:
        self.close()
        self.sock = socket.create_connection(
            (self.host, self.port), timeout=timeout
        )
        self.sock.settimeout(timeout)

    def close(self) -> None:
        sock, self.sock = self.sock, None
        # Detach the buffer without mutating an in-flight reader's bytes.
        self._receive_buffer = bytearray()
        if sock is None:
            return
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        sock.close()

    def set_timeout(self, timeout: float) -> None:
        if self.sock is None:
            raise RuntimeError("socket is not connected")
        self.sock.settimeout(timeout)

    def send_all(self, packet: bytes) -> None:
        if self.sock is None:
            raise RuntimeError("socket is not connected")
        self.sock.sendall(packet)

    def recv_exact(self, size: int) -> bytes:
        sock = self.sock
        if sock is None:
            raise RuntimeError("socket is not connected")
        if size < 0:
            raise ValueError("receive size must not be negative")
        buffer = self._receive_buffer
        timeout = sock.gettimeout()
        deadline = None if timeout is None else time.monotonic() + timeout
        # Keep partial bytes across timeouts, rather than desynchronizing TCP.
        try:
            while len(buffer) < size:
                if deadline is not None:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError("TCP read deadline exceeded")
                    sock.settimeout(remaining)
                chunk = sock.recv(size - len(buffer))
                if self.sock is not sock:
                    raise RuntimeError("socket is closed")
                if not chunk:
                    raise RuntimeError(
                        f"socket closed while reading {size} bytes"
                    )
                buffer.extend(chunk)
        finally:
            if self.sock is sock:
                try:
                    sock.settimeout(timeout)
                except OSError:
                    pass
        result = bytes(buffer[:size])
        if self.sock is not sock:
            raise RuntimeError("socket is closed")
        del buffer[:size]
        return result
