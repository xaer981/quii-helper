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

RTSP_VERSION = "RTSP/1.0"
PUBLIC_METHODS = "OPTIONS, DESCRIBE, SETUP, PLAY, PAUSE, TEARDOWN"


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
    _clients: list[_RtspClient] = field(default_factory=list, init=False)
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
        return f"rtsp://{self._connect_host()}:{self.port}{self.path}"

    @property
    def client_count(self) -> int:
        with self._clients_lock:
            return len(self._clients)

    def publish(self, access_unit: bytes) -> None:
        if not access_unit or not self._running:
            return

        timestamp = self._rtp_timestamp()
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
                self._remove_client(client)

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
            client = _RtspClient(self, client_sock, address)
            with self._clients_lock:
                self._clients.append(client)
            client.start()

    def _remove_client(self, client: "_RtspClient") -> None:
        with self._clients_lock:
            if client in self._clients:
                self._clients.remove(client)
        client.close()

    def _playing_clients(self) -> list["_RtspClient"]:
        with self._clients_lock:
            return [client for client in self._clients if client.playing]

    def _rtp_timestamp(self) -> int:
        elapsed = max(0.0, time.monotonic() - self._started_at)
        return int(elapsed * DEFAULT_RTP_CLOCK_RATE) & 0xFFFFFFFF

    def _connect_host(self) -> str:
        if self.advertised_host:
            return self.advertised_host
        if self.host in {"", "0.0.0.0", "::"}:
            return "127.0.0.1"
        return self.host


class _RtspClient:
    def __init__(
        self,
        server: RtspH264Server,
        sock: socket.socket,
        address: tuple[str, int],
    ) -> None:
        self.server = server
        self.sock = sock
        self.address = address
        self.playing = False
        self.transport = "tcp"
        self.interleaved_rtp_channel = 0
        self.udp_rtp_target: tuple[str, int] | None = None
        self.udp_rtp_sock: socket.socket | None = None
        self.udp_rtcp_sock: socket.socket | None = None
        self._send_lock = threading.RLock()
        self._thread = threading.Thread(
            target=self._run,
            name=f"quii-rtsp-client-{address[0]}:{address[1]}",
            daemon=True,
        )
        self._closed = False

    def start(self) -> None:
        self.sock.settimeout(0.5)
        self._thread.start()

    def send_rtp_packets(self, packets: list[bytes]) -> bool:
        if self.transport == "udp":
            return self._send_udp_rtp_packets(packets)
        try:
            with self._send_lock:
                for packet in packets:
                    frame = (
                        b"$"
                        + bytes([self.interleaved_rtp_channel & 0xFF])
                        + len(packet).to_bytes(2, "big")
                        + packet
                    )
                    self.sock.sendall(frame)
            return True
        except OSError:
            return False

    def _send_udp_rtp_packets(self, packets: list[bytes]) -> bool:
        if self.udp_rtp_sock is None or self.udp_rtp_target is None:
            return False
        try:
            for packet in packets:
                self.udp_rtp_sock.sendto(packet, self.udp_rtp_target)
            return True
        except OSError:
            return False

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.playing = False
        for udp_sock in (self.udp_rtp_sock, self.udp_rtcp_sock):
            if udp_sock is not None:
                try:
                    udp_sock.close()
                except OSError:
                    pass
        self.udp_rtp_sock = None
        self.udp_rtcp_sock = None
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self.sock.close()
        except OSError:
            pass

    def _run(self) -> None:
        buffer = b""
        try:
            while not self._closed and not self.server._stop_event.is_set():
                try:
                    chunk = self.sock.recv(4096)
                except socket.timeout:
                    continue
                except OSError:
                    break
                if not chunk:
                    break
                buffer += chunk
                while b"\r\n\r\n" in buffer:
                    raw_request, buffer = buffer.split(b"\r\n\r\n", 1)
                    try:
                        self._handle_request(raw_request.decode("latin1"))
                    except OSError:
                        return
        finally:
            self.server._remove_client(self)

    def _handle_request(self, request_text: str) -> None:
        request = _parse_request(request_text)
        if request is None:
            self._send_response(400, "Bad Request", cseq="0")
            return

        method = request.method.upper()
        if method == "OPTIONS":
            self._send_response(
                200,
                "OK",
                cseq=request.cseq,
                headers={"Public": PUBLIC_METHODS},
            )
            return
        if method == "DESCRIBE":
            body = self._sdp_description()
            self._send_response(
                200,
                "OK",
                cseq=request.cseq,
                headers={"Content-Type": "application/sdp"},
                body=body,
            )
            return
        if method == "SETUP":
            self._handle_setup(request)
            return
        if method == "PLAY":
            self.playing = True
            self._send_response(
                200,
                "OK",
                cseq=request.cseq,
                headers={
                    "Session": self.server.session_id,
                    "RTP-Info": (
                        f"url={self.server.url}/trackID=0;"
                        f"seq={self.server._sequence_number & 0xFFFF};"
                        f"rtptime={self.server._rtp_timestamp()}"
                    ),
                },
            )
            return
        if method == "PAUSE":
            self.playing = False
            self._send_response(
                200,
                "OK",
                cseq=request.cseq,
                headers={"Session": self.server.session_id},
            )
            return
        if method == "TEARDOWN":
            self._send_response(
                200,
                "OK",
                cseq=request.cseq,
                headers={"Session": self.server.session_id},
            )
            self.close()
            return

        self._send_response(405, "Method Not Allowed", cseq=request.cseq)

    def _handle_setup(self, request: "_RtspRequest") -> None:
        transport = request.headers.get("transport", "")
        transport_upper = transport.upper()
        if "RTP/AVP/TCP" in transport_upper:
            self._setup_tcp_transport(request, transport)
            return
        if "RTP/AVP" in transport_upper:
            self._setup_udp_transport(request, transport)
            return

        self._send_response(
            461,
            "Unsupported Transport",
            cseq=request.cseq,
        )

    def _setup_tcp_transport(
        self, request: "_RtspRequest", transport: str
    ) -> None:
        self.transport = "tcp"
        self.interleaved_rtp_channel = _interleaved_channel(transport)
        self._send_response(
            200,
            "OK",
            cseq=request.cseq,
            headers={
                "Transport": (
                    "RTP/AVP/TCP;unicast;"
                    f"interleaved={self.interleaved_rtp_channel}-"
                    f"{self.interleaved_rtp_channel + 1}"
                ),
                "Session": self.server.session_id,
            },
        )

    def _setup_udp_transport(
        self, request: "_RtspRequest", transport: str
    ) -> None:
        client_ports = _client_ports(transport)
        if client_ports is None:
            self._send_response(
                461,
                "Unsupported Transport",
                cseq=request.cseq,
            )
            return

        self.transport = "udp"
        self.udp_rtp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_rtcp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_rtp_sock.bind((self.server.host, 0))
        self.udp_rtcp_sock.bind((self.server.host, 0))
        server_rtp_port = self.udp_rtp_sock.getsockname()[1]
        server_rtcp_port = self.udp_rtcp_sock.getsockname()[1]
        self.udp_rtp_target = (self.address[0], client_ports[0])
        self._send_response(
            200,
            "OK",
            cseq=request.cseq,
            headers={
                "Transport": (
                    "RTP/AVP;unicast;"
                    f"client_port={client_ports[0]}-{client_ports[1]};"
                    f"server_port={server_rtp_port}-{server_rtcp_port};"
                    f"ssrc={self.server.ssrc:08X}"
                ),
                "Session": self.server.session_id,
            },
        )

    def _send_response(
        self,
        code: int,
        reason: str,
        *,
        cseq: str,
        headers: dict[str, str] | None = None,
        body: str = "",
    ) -> None:
        response_headers = {
            "CSeq": cseq,
            "Server": "quii-helper",
            **(headers or {}),
        }
        body_bytes = body.encode("utf-8")
        if body:
            response_headers["Content-Length"] = str(len(body_bytes))

        lines = [f"{RTSP_VERSION} {code} {reason}"]
        lines.extend(
            f"{name}: {value}" for name, value in response_headers.items()
        )
        response = ("\r\n".join(lines) + "\r\n\r\n").encode("utf-8")
        if body_bytes:
            response += body_bytes
        with self._send_lock:
            self.sock.sendall(response)

    def _sdp_description(self) -> str:
        return "\r\n".join(
            [
                "v=0",
                f"o=- 0 0 IN IP4 {self.server._connect_host()}",
                "s=QUII Camera",
                "t=0 0",
                "a=control:*",
                f"m=video 0 RTP/AVP {self.server.payload_type}",
                (
                    f"a=rtpmap:{self.server.payload_type} "
                    f"H264/{DEFAULT_RTP_CLOCK_RATE}"
                ),
                f"a=fmtp:{self.server.payload_type} packetization-mode=1",
                "a=control:trackID=0",
                "",
            ]
        )


@dataclass(frozen=True)
class _RtspRequest:
    method: str
    uri: str
    version: str
    cseq: str
    headers: dict[str, str]


def _parse_request(request_text: str) -> _RtspRequest | None:
    lines = [line for line in request_text.split("\r\n") if line]
    if not lines:
        return None
    parts = lines[0].split()
    if len(parts) != 3:
        return None

    headers = {}
    for line in lines[1:]:
        if ":" not in line:
            continue
        name, value = line.split(":", 1)
        headers[name.strip().lower()] = value.strip()

    return _RtspRequest(
        method=parts[0],
        uri=parts[1],
        version=parts[2],
        cseq=headers.get("cseq", "0"),
        headers=headers,
    )


def _interleaved_channel(transport: str) -> int:
    marker = "interleaved="
    lower = transport.lower()
    start = lower.find(marker)
    if start < 0:
        return 0
    value = transport[start + len(marker) :].split(";", 1)[0]
    first = value.split("-", 1)[0]
    try:
        return int(first)
    except ValueError:
        return 0


def _client_ports(transport: str) -> tuple[int, int] | None:
    marker = "client_port="
    lower = transport.lower()
    start = lower.find(marker)
    if start < 0:
        return None
    value = transport[start + len(marker) :].split(";", 1)[0]
    parts = value.split("-", 1)
    if len(parts) != 2:
        return None
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return None


def _normalize_path(path: str) -> str:
    if not path:
        return "/live"
    return path if path.startswith("/") else f"/{path}"
