from __future__ import annotations

import socket
import threading
import time
from collections import deque
from contextlib import ExitStack
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from quii_helper.streaming.rtsp.constants import PUBLIC_METHODS, RTSP_VERSION
from quii_helper.streaming.rtsp.request import (
    RtspRequest,
    RtspRequestBuffer,
    parse_request,
)
from quii_helper.streaming.rtsp.sdp import build_h264_sdp
from quii_helper.streaming.rtsp.transport import (
    RtpTransport,
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
        self.tracks = {0: RtpTransport()}
        self._setup_tracks: set[int] = set()
        self._waiting_keyframe = server.audio
        self._send_lock = threading.RLock()
        self._outgoing_condition = threading.Condition()
        self._outgoing: deque[tuple[list[bytes], int, float, int]] = deque()
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

    def enqueue_rtp_packets(
        self, packets: list[bytes], *, track_id: int = 0, keyframe: bool = True
    ) -> bool:
        """Queue a complete access unit without blocking the camera producer."""
        size = sum(len(packet) for packet in packets)
        with self._outgoing_condition:
            if self._closed:
                return False
            if not self.playing:
                return True
            if (
                self._setup_tracks and track_id not in self._setup_tracks
            ) or track_id not in self.tracks:
                return True
            if track_id == 0 and self._waiting_keyframe:
                if not keyframe:
                    return True
                self._waiting_keyframe = False
            if (
                len(self._outgoing) >= MAX_QUEUED_ACCESS_UNITS
                or self._outgoing_bytes + size > MAX_QUEUED_RTP_BYTES
            ):
                return False
            self._outgoing.append((packets, size, time.monotonic(), track_id))
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
                    packets, size, enqueued_at, track_id = (
                        self._outgoing.popleft()
                    )
                with self._send_lock:
                    if self.playing and not self.send_rtp_packets(
                        packets,
                        deadline=enqueued_at + MAX_CLIENT_LAG_SECONDS,
                        track_id=track_id,
                    ):
                        return
                with self._outgoing_condition:
                    if not self._closed:
                        self._outgoing_bytes -= size
        finally:
            self.server.remove_client(self)

    def send_rtp_packets(
        self,
        packets: list[bytes],
        *,
        deadline: float | None = None,
        track_id: int = 0,
    ) -> bool:
        try:
            with self._send_lock:
                if self._closed:
                    return False
                track = self.tracks.get(track_id)
                if track is None:
                    return False
                if track.mode == "udp":
                    return self._send_udp_rtp_packets(
                        packets, deadline=deadline, track_id=track_id
                    )
                for packet in packets:
                    if self._closed or (
                        deadline is not None and time.monotonic() >= deadline
                    ):
                        return False
                    frame = (
                        b"$"
                        + bytes([track.channel & 0xFF])
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
        for track_id in list(self.tracks):
            self._close_udp_transport(track_id)

    def _close_udp_transport(self, track_id: int = 0) -> None:
        with self._outgoing_condition:
            self.tracks[track_id].close()

    def _send_udp_rtp_packets(
        self,
        packets: list[bytes],
        *,
        deadline: float | None = None,
        track_id: int = 0,
    ) -> bool:
        track = self.tracks[track_id]
        sock, target = track.rtp_sock, track.target
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
            if self.server.audio and (
                not self.server.audio_ready.wait(5.0)
                or self.server.audio_format is None
            ):
                self._send_response(
                    503,
                    "Service Unavailable",
                    cseq=request.cseq,
                    headers={"Retry-After": "1"},
                )
                return
            if self.server.audio and (
                not self.server.video_ready.wait(5.0)
                or not self.server.parameter_sets
            ):
                self._send_response(
                    503,
                    "Service Unavailable",
                    cseq=request.cseq,
                    headers={"Retry-After": "1"},
                )
                return
            body = build_h264_sdp(
                connect_host=self.server.connect_host,
                payload_type=self.server.payload_type,
                audio_format=self.server.audio_format,
                parameter_sets=self.server.parameter_sets,
            )
            self._send_response(
                200,
                "OK",
                cseq=request.cseq,
                headers={
                    "Content-Type": "application/sdp",
                    "Content-Base": urlsplit(request.uri)
                    ._replace(
                        path=self.server.path.rstrip("/") + "/",
                        query="",
                        fragment="",
                    )
                    .geturl(),
                },
                body=body,
            )
            return
        if method == "SETUP":
            self._handle_setup(request)
            return
        if method == "PLAY":
            with self._send_lock:
                self._waiting_keyframe = self.server.audio
                self.playing = True
                self._send_response(
                    200,
                    "OK",
                    cseq=request.cseq,
                    # Live keyframe gating makes the first RTP packet unknown.
                    headers={"Session": self.server.session_id},
                )
            return
        if method == "PAUSE":
            with self._send_lock:
                self.playing = False
                with self._outgoing_condition:
                    self._outgoing_bytes -= sum(
                        size for _, size, _, _ in self._outgoing
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
            path = urlsplit(request.uri).path.rstrip("/") or "/"
            base = self.server.path.rstrip("/")
            paths = {base or "/": 0, f"{base}/trackID=0": 0}
            if self.server.audio_format is not None:
                paths[f"{base}/trackID=1"] = 1
            track_id = paths.get(path)
            if track_id is None:
                self._send_response(404, "Not Found", cseq=request.cseq)
                return
            self.tracks.setdefault(
                track_id, RtpTransport(channel=2 * track_id)
            )
            transport = request.headers.get("transport", "")
            transport_upper = transport.upper()
            if "RTP/AVP/TCP" in transport_upper:
                self._setup_tcp_transport(
                    request, transport, track_id=track_id
                )
                return
            if "RTP/AVP" in transport_upper:
                self._setup_udp_transport(
                    request, transport, track_id=track_id
                )
                return

            self._send_response(
                461,
                "Unsupported Transport",
                cseq=request.cseq,
            )

    def _setup_tcp_transport(
        self, request: RtspRequest, transport: str, *, track_id: int = 0
    ) -> None:
        channel = interleaved_channel(transport)
        if "interleaved=" not in transport.lower():
            channel = track_id * 2
        if channel is not None and any(
            other != track_id
            and self.tracks[other].mode == "tcp"
            and {channel, channel + 1}
            & {self.tracks[other].channel, self.tracks[other].channel + 1}
            for other in self._setup_tracks
        ):
            channel = None
        if channel is None:
            self._send_response(
                461, "Unsupported Transport", cseq=request.cseq
            )
            return
        self._close_udp_transport(track_id)
        track = self.tracks[track_id]
        track.mode = "tcp"
        track.channel = channel
        self._setup_tracks.add(track_id)
        self._send_response(
            200,
            "OK",
            cseq=request.cseq,
            headers={
                "Transport": (
                    "RTP/AVP/TCP;unicast;"
                    f"interleaved={track.channel}-"
                    f"{track.channel + 1}"
                ),
                "Session": self.server.session_id,
            },
        )

    def _setup_udp_transport(
        self, request: RtspRequest, transport: str, *, track_id: int = 0
    ) -> None:
        ports = client_ports(transport)
        if ports is None:
            self._send_response(
                461,
                "Unsupported Transport",
                cseq=request.cseq,
            )
            return

        self._close_udp_transport(track_id)
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
                track = self.tracks[track_id]
                track.mode = "udp"
                track.rtp_sock, track.rtcp_sock = rtp, rtcp
                track.target = (self.address[0], ports[0])
                self._setup_tracks.add(track_id)
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
                    f"ssrc={self.server.track_ssrc(track_id):08X}"
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
