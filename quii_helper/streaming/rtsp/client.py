from __future__ import annotations

import socket
import threading
import time
from collections import deque
from contextlib import ExitStack
from typing import TYPE_CHECKING

from quii_helper.streaming.rtsp.constants import PUBLIC_METHODS, RTSP_VERSION
from quii_helper.streaming.rtsp.request import (
    RtspRequest,
    RtspRequestBuffer,
    parse_request,
)
from quii_helper.streaming.rtsp.sdp import build_h264_sdp
from quii_helper.streaming.rtsp.transport import (
    client_ports,
    interleaved_channel,
)

if TYPE_CHECKING:
    from quii_helper.streaming.rtsp.server import RtspH264Server

REQUEST_TIMEOUT_SECONDS = 10.0
MAX_QUEUED_ACCESS_UNITS = 32
MAX_QUEUED_RTP_BYTES = 4 * 1024 * 1024
MAX_CLIENT_LAG_SECONDS = 2.0


class RtspClient:
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
        self._outgoing_condition = threading.Condition()
        self._outgoing: deque[tuple[list[bytes], int, float]] = deque()
        self._outgoing_bytes = 0
        self._sender_thread = threading.Thread(
            target=self._send_loop,
            name=f"quii-rtsp-send-{address[0]}:{address[1]}",
            daemon=True,
        )
        self._thread = threading.Thread(
            target=self._run,
            name=f"quii-rtsp-client-{address[0]}:{address[1]}",
            daemon=True,
        )
        self._closed = False

    def start(self) -> None:
        self.sock.settimeout(0.5)
        try:
            self._thread.start()
            self._sender_thread.start()
        except BaseException:
            self.close()
            raise

    def enqueue_rtp_packets(self, packets: list[bytes]) -> bool:
        """Queue a complete access unit without blocking the camera producer."""
        size = sum(len(packet) for packet in packets)
        with self._outgoing_condition:
            if self._closed:
                return False
            if not self.playing:
                return True
            if (
                len(self._outgoing) >= MAX_QUEUED_ACCESS_UNITS
                or self._outgoing_bytes + size > MAX_QUEUED_RTP_BYTES
            ):
                return False
            self._outgoing.append((packets, size, time.monotonic()))
            self._outgoing_bytes += size
            self._outgoing_condition.notify()
            return True

    def _send_loop(self) -> None:
        try:
            while True:
                with self._outgoing_condition:
                    self._outgoing_condition.wait_for(
                        lambda: self._closed or bool(self._outgoing)
                    )
                    if self._closed:
                        return
                    packets, size, enqueued_at = self._outgoing.popleft()
                with self._send_lock:
                    if self.playing and not self.send_rtp_packets(
                        packets, deadline=enqueued_at + MAX_CLIENT_LAG_SECONDS
                    ):
                        return
                with self._outgoing_condition:
                    if not self._closed:
                        self._outgoing_bytes -= size
        finally:
            self.server.remove_client(self)

    def send_rtp_packets(
        self, packets: list[bytes], *, deadline: float | None = None
    ) -> bool:
        try:
            with self._send_lock:
                if self._closed:
                    return False
                if self.transport == "udp":
                    return self._send_udp_rtp_packets(
                        packets, deadline=deadline
                    )
                for packet in packets:
                    if self._closed or (
                        deadline is not None and time.monotonic() >= deadline
                    ):
                        return False
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

    def close(self) -> None:
        with self._outgoing_condition:
            if self._closed:
                return
            self._closed = True
            self.playing = False
            self._outgoing.clear()
            self._outgoing_bytes = 0
            self._outgoing_condition.notify_all()
        # Interrupt a blocked send before waiting for any sender-owned lock.
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self.sock.close()
        except OSError:
            pass
        self._close_udp_transport()

    def _close_udp_transport(self) -> None:
        with self._outgoing_condition:
            sockets = self.udp_rtp_sock, self.udp_rtcp_sock
            self.udp_rtp_sock = None
            self.udp_rtcp_sock = None
            self.udp_rtp_target = None
        for udp_sock in sockets:
            if udp_sock is not None:
                try:
                    udp_sock.close()
                except OSError:
                    pass

    def _send_udp_rtp_packets(
        self, packets: list[bytes], *, deadline: float | None = None
    ) -> bool:
        sock, target = self.udp_rtp_sock, self.udp_rtp_target
        if sock is None or target is None:
            return False
        try:
            for packet in packets:
                if self._closed or (
                    deadline is not None and time.monotonic() >= deadline
                ):
                    return False
                sock.sendto(packet, target)
            return True
        except OSError:
            return False

    def _run(self) -> None:
        buffer = RtspRequestBuffer()
        pending_since: float | None = None
        try:
            while not self._closed and not self.server.stop_event.is_set():
                if (
                    pending_since is not None
                    and time.monotonic() - pending_since
                    >= REQUEST_TIMEOUT_SECONDS
                ):
                    break
                try:
                    chunk = self.sock.recv(4096)
                except socket.timeout:
                    continue
                except OSError:
                    break
                if not chunk:
                    break
                try:
                    requests = buffer.feed(chunk)
                    for request in requests:
                        if self._closed:
                            break
                        self._handle_request(request)
                except ValueError:
                    self._send_response(400, "Bad Request", cseq="0")
                    return
                pending_since = (
                    (pending_since or time.monotonic())
                    if buffer.pending
                    else None
                )
        except OSError:
            return
        finally:
            self.server.remove_client(self)

    def _handle_request(self, request_text: str) -> None:
        request = parse_request(request_text)
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
            body = build_h264_sdp(
                connect_host=self.server.connect_host,
                payload_type=self.server.payload_type,
            )
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
            with self._send_lock:
                self.playing = True
                self._send_response(
                    200,
                    "OK",
                    cseq=request.cseq,
                    headers={
                        "Session": self.server.session_id,
                        "RTP-Info": (
                            f"url={self.server.url}/trackID=0;"
                            f"seq={self.server.sequence_number & 0xFFFF};"
                            f"rtptime={self.server.rtp_timestamp()}"
                        ),
                    },
                )
            return
        if method == "PAUSE":
            with self._send_lock:
                self.playing = False
                with self._outgoing_condition:
                    self._outgoing_bytes -= sum(
                        size for _, size, _ in self._outgoing
                    )
                    self._outgoing.clear()
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

    def _handle_setup(self, request: RtspRequest) -> None:
        with self._send_lock:
            if self._closed:
                return
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
        self, request: RtspRequest, transport: str
    ) -> None:
        channel = interleaved_channel(transport)
        if channel is None:
            self._send_response(
                461, "Unsupported Transport", cseq=request.cseq
            )
            return
        self._close_udp_transport()
        self.transport = "tcp"
        self.interleaved_rtp_channel = channel
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
        self, request: RtspRequest, transport: str
    ) -> None:
        ports = client_ports(transport)
        if ports is None:
            self._send_response(
                461,
                "Unsupported Transport",
                cseq=request.cseq,
            )
            return

        self._close_udp_transport()
        self.transport = "udp"
        with ExitStack() as stack:
            rtp = stack.enter_context(
                socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            )
            rtcp = stack.enter_context(
                socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            )
            rtp.settimeout(0.5)
            rtcp.settimeout(0.5)
            rtp.bind((self.server.host, 0))
            rtcp.bind((self.server.host, 0))
            server_rtp_port = rtp.getsockname()[1]
            server_rtcp_port = rtcp.getsockname()[1]
            with self._outgoing_condition:
                if self._closed:
                    return
                self.udp_rtp_sock, self.udp_rtcp_sock = rtp, rtcp
                self.udp_rtp_target = (self.address[0], ports[0])
                stack.pop_all()
        self._send_response(
            200,
            "OK",
            cseq=request.cseq,
            headers={
                "Transport": (
                    "RTP/AVP;unicast;"
                    f"client_port={ports[0]}-{ports[1]};"
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
