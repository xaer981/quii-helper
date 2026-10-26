from __future__ import annotations

import secrets
import socket
import threading
import time
from base64 import b64encode
from dataclasses import dataclass, field
from typing import Any

from quii_helper.media.audio import CameraAudioFrame
from quii_helper.streaming.rtp.clock import RtpMediaClock
from quii_helper.streaming.rtp.g711 import G711Format, packetize_g711
from quii_helper.streaming.rtp.h264 import (
    DEFAULT_H264_PAYLOAD_TYPE,
    DEFAULT_MAX_RTP_PAYLOAD_SIZE,
    DEFAULT_RTP_CLOCK_RATE,
    annexb_nal_units,
    packetize_h264_access_unit,
)
from quii_helper.streaming.rtsp.client import RtspClient

MAX_RTSP_CLIENTS = 32


@dataclass
class RtspH264Server:
    host: str = "127.0.0.1"
    port: int = 8554
    path: str = "/live"
    advertised_host: str | None = None
    payload_type: int = DEFAULT_H264_PAYLOAD_TYPE
    max_payload_size: int = DEFAULT_MAX_RTP_PAYLOAD_SIZE
    audio: bool = field(default=False, kw_only=True)
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
    audio_format: G711Format | None = field(default=None, init=False)
    audio_ready: threading.Event = field(
        default_factory=threading.Event, init=False, repr=False
    )
    _audio_ssrc: int = field(
        default_factory=lambda: secrets.randbits(32), init=False
    )
    _audio_sequence: int = field(
        default_factory=lambda: secrets.randbits(16), init=False
    )
    _audio_timestamp: int | None = field(default=None, init=False)
    _media_clock: RtpMediaClock = field(
        default_factory=RtpMediaClock, init=False
    )
    _sps: bytes = field(default=b"", init=False)
    _pps: bytes = field(default=b"", init=False)
    video_ready: threading.Event = field(
        default_factory=threading.Event, init=False, repr=False
    )

    def start(self) -> "RtspH264Server":
        if self._running:
            return self

        self.path = _normalize_path(self.path)
        self._stop_event.clear()
        self.audio_ready.clear()
        self.audio_format = None
        self._audio_timestamp = None
        if self._audio_ssrc == self.ssrc:
            self._audio_ssrc = (self.ssrc + 1) & 0xFFFFFFFF
        self._media_clock = RtpMediaClock()
        self._sps = self._pps = b""
        self.video_ready.clear()
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._sock.bind((self.host, self.port))
            self._sock.listen()
            self._sock.settimeout(0.25)
        except BaseException:
            self._sock.close()
            self._sock = None
            raise
        self.port = int(self._sock.getsockname()[1])
        self._started_at = time.monotonic()
        self._running = True
        self._accept_thread = threading.Thread(
            target=self._accept_loop,
            name="quii-rtsp-accept",
            daemon=True,
        )
        try:
            self._accept_thread.start()
        except BaseException:
            self._accept_thread = None
            self.close()
            raise
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

    @property
    def parameter_sets(self) -> str:
        """Bounded H.264 decoder configuration for a joining RTSP viewer."""
        if not self._sps or not self._pps:
            return ""
        return (
            b64encode(self._sps).decode("ascii")
            + ","
            + b64encode(self._pps).decode("ascii")
        )

    def publish_frame(self, access_unit: bytes, frame: dict[str, Any]) -> None:
        """Publish video on the same native-timestamp timeline as audio."""
        timestamp = self._media_clock.timestamp(
            frame["frame_stamp"], frame["frame_ms"], DEFAULT_RTP_CLOCK_RATE
        )
        self.publish(access_unit, timestamp=timestamp)

    def publish(
        self, access_unit: bytes, *, timestamp: int | None = None
    ) -> None:
        if not access_unit or not self._running:
            return

        units = annexb_nal_units(access_unit)
        keyframe = any(unit[0] & 31 == 5 for unit in units)
        for unit in units:
            if unit[0] & 31 == 7 and len(unit) <= 4096:
                self._sps = unit
            elif unit[0] & 31 == 8 and len(unit) <= 4096:
                self._pps = unit
        if self._sps and self._pps:
            self.video_ready.set()
        timestamp = self.rtp_timestamp() if timestamp is None else timestamp
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
            if not client.enqueue_rtp_packets(
                result.packets, keyframe=keyframe
            ):
                self.remove_client(client)

    def publish_audio(self, frame: CameraAudioFrame) -> None:
        """Publish native G.711 bytes on track 1 without another camera session."""
        if not self.audio or not self._running:
            return
        profile = G711Format.from_frame(frame)
        if self.audio_format is not None and self.audio_format != profile:
            raise ValueError("RTSP audio format changed; restart the stream")
        self.audio_format = profile
        self.audio_ready.set()
        if self._audio_timestamp is None:
            self._audio_timestamp = self._media_clock.timestamp(
                frame.frame_stamp, frame.milliseconds, 8000
            )
        # Native audio timestamps jitter; continuous G.711 follows sample count.
        result = packetize_g711(
            frame.data,
            payload_type=profile.payload_type,
            sequence_number=self._audio_sequence,
            timestamp=self._audio_timestamp,
            ssrc=self._audio_ssrc,
            max_payload_size=self.max_payload_size,
        )
        self._audio_sequence = result.next_sequence_number
        self._audio_timestamp = (
            self._audio_timestamp + len(frame.data)
        ) & 0xFFFFFFFF
        for client in self._playing_clients():
            if not client.enqueue_rtp_packets(result.packets, track_id=1):
                self.remove_client(client)

    def track_ssrc(self, track_id: int) -> int:
        """Return the SSRC actually used by this track's RTP packets."""
        return self.ssrc if track_id == 0 else self._audio_ssrc

    def close(self) -> None:
        with self._clients_lock:
            self._stop_event.set()
            self.audio_ready.set()
            self.video_ready.set()
            self._running = False
            sock, self._sock = self._sock, None
            thread, self._accept_thread = self._accept_thread, None
            clients = list(self._clients)
            self._clients.clear()
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=1.0)
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
                if (
                    self._stop_event.is_set()
                    or len(self._clients) >= MAX_RTSP_CLIENTS
                ):
                    client.close()
                    continue
                self._clients.append(client)
                try:
                    client.start()
                except RuntimeError:
                    self._clients.remove(client)
                    client.close()

    def _playing_clients(self) -> list[RtspClient]:
        with self._clients_lock:
            return [client for client in self._clients if client.playing]


def _normalize_path(path: str) -> str:
    if not path:
        return "/live"
    return "/" + path.strip("/")
