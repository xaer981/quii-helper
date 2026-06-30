from __future__ import annotations

import socket
import threading
from typing import TYPE_CHECKING

from quii_helper.streaming.rtsp.constants import PUBLIC_METHODS, RTSP_VERSION
from quii_helper.streaming.rtsp.request import RtspRequest, parse_request
from quii_helper.streaming.rtsp.sdp import build_h264_sdp
from quii_helper.streaming.rtsp.transport import (
    client_ports,
    interleaved_channel,
)

if TYPE_CHECKING:
    from quii_helper.streaming.rtsp.server import RtspH264Server


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

    def _send_udp_rtp_packets(self, packets: list[bytes]) -> bool:
        if self.udp_rtp_sock is None or self.udp_rtp_target is None:
            return False
        try:
            for packet in packets:
                self.udp_rtp_sock.sendto(packet, self.udp_rtp_target)
            return True
        except OSError:
            return False

    def _run(self) -> None:
        buffer = b""
        try:
            while not self._closed and not self.server.stop_event.is_set():
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

    def _handle_setup(self, request: RtspRequest) -> None:
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
        self.transport = "tcp"
        self.interleaved_rtp_channel = interleaved_channel(transport)
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

        self.transport = "udp"
        self.udp_rtp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_rtcp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_rtp_sock.bind((self.server.host, 0))
        self.udp_rtcp_sock.bind((self.server.host, 0))
        server_rtp_port = self.udp_rtp_sock.getsockname()[1]
        server_rtcp_port = self.udp_rtcp_sock.getsockname()[1]
        self.udp_rtp_target = (self.address[0], ports[0])
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
