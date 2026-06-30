from __future__ import annotations

import secrets
import socket
import threading
import time
from dataclasses import dataclass, field

from quii_helper.streaming.rtp.h264 import (
    DEFAULT_H264_PAYLOAD_TYPE,
    DEFAULT_MAX_RTP_PAYLOAD_SIZE,
    DEFAULT_RTP_CLOCK_RATE,
    packetize_h264_access_unit,
)
from quii_helper.streaming.rtsp.client import RtspClient


@dataclass
class RtspH264Server:
    host: str = "0.0.0.0"
    port: int = 8554
    path: str = "/live"
    advertised_host: str | None = None
    payload_type: int = DEFAULT_H264_PAYLOAD_TYPE
    max_payload_size: int = DEFAULT_MAX_RTP_PAYLOAD_SIZE
    ssrc: int = field(default_factory=lambda: secrets.randbits(32))
    session_id: str = field(
        default_factory=lambda: secrets.token_hex(8), init=False
    )
    _sock: socket.socket | None = field(default=None, init=False, repr=False)
    _accept_thread: threading.Thread | None = field(
        default=None, init=False, repr=False
    )
    _clients: list[RtspClient] = field(default_factory=list, init=False)
    _clients_lock: threading.RLock = field(
        default_factory=threading.RLock, init=False, repr=False
    )
    _stop_event: threading.Event = field(
        default_factory=threading.Event, init=False, repr=False
    )
    _started_at: float = field(default=0.0, init=False)
    _sequence_number: int = field(
        default_factory=lambda: secrets.randbits(16), init=False
    )
    _running: bool = field(default=False, init=False)

    def start(self) -> "RtspH264Server":
        if self._running:
            return self

        self.path = _normalize_path(self.path)
        self._stop_event.clear()
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((self.host, self.port))
        self._sock.listen()
        self._sock.settimeout(0.25)
        self.port = int(self._sock.getsockname()[1])
        self._started_at = time.monotonic()
        self._running = True
        self._accept_thread = threading.Thread(
            target=self._accept_loop,
            name="quii-rtsp-accept",
            daemon=True,
        )
        self._accept_thread.start()
        return self

    @property
    def url(self) -> str:
        return f"rtsp://{self.connect_host}:{self.port}{self.path}"

    @property
    def connect_host(self) -> str:
        if self.advertised_host:
            return self.advertised_host
        if self.host in {"", "0.0.0.0", "::"}:
            return "127.0.0.1"
        return self.host

    @property
    def client_count(self) -> int:
        with self._clients_lock:
            return len(self._clients)

    @property
    def sequence_number(self) -> int:
        return self._sequence_number

    @property
    def stop_event(self) -> threading.Event:
        return self._stop_event

    def publish(self, access_unit: bytes) -> None:
        if not access_unit or not self._running:
            return

        timestamp = self.rtp_timestamp()
        result = packetize_h264_access_unit(
            access_unit,
            sequence_number=self._sequence_number,
            timestamp=timestamp,
            ssrc=self.ssrc,
            payload_type=self.payload_type,
            max_payload_size=self.max_payload_size,
        )
        self._sequence_number = result.next_sequence_number
        if not result.packets:
            return

        for client in self._playing_clients():
            if not client.send_rtp_packets(result.packets):
                self.remove_client(client)

    def close(self) -> None:
        self._stop_event.set()
        self._running = False
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

        if self._accept_thread is not None:
            self._accept_thread.join(timeout=1.0)
            self._accept_thread = None

        with self._clients_lock:
            clients = list(self._clients)
            self._clients.clear()
        for client in clients:
            client.close()

    def __enter__(self) -> "RtspH264Server":
        return self.start()

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def remove_client(self, client: RtspClient) -> None:
        with self._clients_lock:
            if client in self._clients:
                self._clients.remove(client)
        client.close()

    def rtp_timestamp(self) -> int:
        elapsed = max(0.0, time.monotonic() - self._started_at)
        return int(elapsed * DEFAULT_RTP_CLOCK_RATE) & 0xFFFFFFFF

    def _accept_loop(self) -> None:
        sock = self._sock
        if sock is None:
            return
        while not self._stop_event.is_set():
            try:
                client_sock, address = sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            client = RtspClient(self, client_sock, address)
            with self._clients_lock:
                self._clients.append(client)
            client.start()

    def _playing_clients(self) -> list[RtspClient]:
        with self._clients_lock:
            return [client for client in self._clients if client.playing]


def _normalize_path(path: str) -> str:
    if not path:
        return "/live"
    return path if path.startswith("/") else f"/{path}"
