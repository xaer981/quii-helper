"""Single-owner native talk transport; only close may run concurrently."""

import hashlib
import hmac
import math
import time
from collections import deque
from collections.abc import Callable
from threading import Event

from quii_helper.config import AutonomousConfig
from quii_helper.device.security.auth import encode_device_password
from quii_helper.models.packets import DecodedQuiiMessage
from quii_helper.protocols.quii.live_envelope import (
    build_live_play_packet_from_body,
)
from quii_helper.protocols.tcp.codec.message_codec import (
    DecodedTcpHeader,
    decode_tcp_header,
    decode_tcp_payload,
)
from quii_helper.protocols.tcp.live.session import validate_lan_config
from quii_helper.protocols.tcp.talk.packets import (
    audio_packet,
    open_packet,
    request_packet,
    setup_packet,
    talk_channel,
)
from quii_helper.protocols.tcp.transport.client import TcpTransportFactory
from quii_helper.protocols.tcp.transport.socket_transport import (
    TcpSocketTransport,
)
from quii_helper.support.errors import ConfigurationError, QuiiConnectionError

MAX_MEDIA_BYTES = 65535 + 20
MAX_STARTUP_MESSAGES = 16


class LanTalkSession:
    """Own a separate LAN TCP connection with supplied key/auth credentials.

    Supports AES-256/SHA256, G.711 A-law/mu-law at 8000 Hz mono, and both
    native outgoing packet layouts. Unsupported negotiation fails closed.
    There is no cloud fallback, automatic retry, microphone or file I/O.
    An optional diagnostic observer sees validated messages, including early
    media before ready, once per wire message rather than once per dequeue.
    """

    def __init__(
        self,
        config: AutonomousConfig,
        *,
        channel: int | None = None,
        transport_factory: TcpTransportFactory = TcpSocketTransport,
        message_observer: Callable[[DecodedQuiiMessage], None] | None = None,
    ) -> None:
        validate_lan_config(config)
        try:
            self.channel = talk_channel(65535 if channel is None else channel)
        except ValueError as exc:
            raise ConfigurationError(str(exc)) from exc
        self.config = config
        self._key = config.stream_key.encode("utf-8")
        self._password = encode_device_password(config.auth_code)
        self._transport = transport_factory(
            config.device_host, config.stream_port
        )
        self._closed = Event()
        self._message_observer = message_observer
        self.ready = False
        self.codec: int | None = None
        self.full_packet = False
        self.receiving = False
        self._pending_receive: bool | None = None
        self._receive_deadline = 0.0
        self._pending_header: DecodedTcpHeader | None = None
        self._startup: deque[DecodedQuiiMessage] = deque()
        self._last_keepalive = 0.0
        self._handshake: dict[str, int | None] = {
            "setup_status": None,
            "crypto_mode": None,
            "sha_mode": None,
            "open_status": None,
            "codec_mask": None,
            "c_status": None,
            "d_status": None,
        }

    @property
    def handshake_diagnostics(self) -> dict[str, int | None]:
        """Copy status fields, retained after close; command replies passed SHA.

        Setup is unencrypted. Missing C/D replies remain None, not success.
        No authentication body, key or received media is exposed.
        """
        return dict(self._handshake)

    def open(self) -> "LanTalkSession":
        """Wait for setup, Open and native ready (0x0D), preserving early media."""
        self._check_closed()
        if self.ready:
            return self
        deadline = time.monotonic() + self.config.connect_timeout
        try:
            self._transport.connect(timeout=self._remaining(deadline))
            self._check_closed()
            self._send(setup_packet(), deadline=deadline)
            raw = self._read_exact(32, deadline)
            if raw[0] == 0xA9:
                self._handshake.update(
                    setup_status=raw[9], crypto_mode=raw[10], sha_mode=raw[11]
                )
            if raw[0] != 0xA9 or raw[9] != 0:
                raise QuiiConnectionError("LAN talk setup rejected")
            if raw[10:12] != b"\x02\x01":
                raise QuiiConnectionError("LAN talk requires AES-256/SHA256")
            self._send(
                open_packet(self.channel, self._password, self._key),
                deadline=deadline,
            )
            while self.codec is None:
                self._preserve_startup(self._read_message(deadline))
            self._send(
                request_packet(
                    self.channel,
                    sending=True,
                    enabled=True,
                    codec=self.codec,
                    key=self._key,
                ),
                deadline=deadline,
            )
            self._pending_receive = True
            self._receive_deadline = deadline
            self._send(
                request_packet(
                    self.channel,
                    sending=False,
                    enabled=True,
                    codec=self.codec,
                    key=self._key,
                ),
                deadline=deadline,
            )
            while not self.ready:
                self._preserve_startup(self._read_message(deadline))
            self._check_closed()
            self._last_keepalive = time.monotonic()
            return self
        except BaseException as exc:
            self.close()
            if isinstance(
                exc, (OSError, RuntimeError, ValueError)
            ) and not isinstance(exc, QuiiConnectionError):
                raise QuiiConnectionError(
                    "LAN talk startup failed; no fallback attempted"
                ) from exc
            raise

    def _preserve_startup(self, message: DecodedQuiiMessage) -> None:
        if message["is_media"]:
            if len(self._startup) >= MAX_STARTUP_MESSAGES:
                raise QuiiConnectionError(
                    "too much LAN talk media before ready"
                )
            self._startup.append(message)

    @property
    def receive_pending(self) -> bool:
        """Whether a serialized incoming-audio request awaits an ACK."""
        return self._pending_receive is not None

    def request_receive(self, enabled: bool) -> None:
        """Enable/disable incoming audio; continue receiving to validate its ACK."""
        self._check_ready()
        if self.receive_pending:
            raise QuiiConnectionError("LAN talk receive request is pending")
        self._pending_receive = enabled
        self._receive_deadline = time.monotonic() + self.config.connect_timeout
        try:
            assert self.codec is not None
            self._send(
                request_packet(
                    self.channel,
                    sending=False,
                    enabled=enabled,
                    codec=self.codec,
                    key=self._key,
                ),
                deadline=self._receive_deadline,
            )
        except BaseException:
            self.close()
            raise

    def send_audio(self, encoded: bytes) -> None:
        """Send one encoded 40ms frame; the coordinator owns pacing."""
        self._check_ready()
        assert self.codec is not None
        packet = audio_packet(
            encoded,
            codec=self.codec,
            full_packet=self.full_packet,
            key=self._key,
        )
        try:
            self._send(
                packet, deadline=time.monotonic() + self.config.connect_timeout
            )
        except BaseException:
            self.close()
            raise

    def recv_message(self, *, timeout: float = 1.0) -> DecodedQuiiMessage:
        """Read one message; partial TCP data survives ordinary read timeouts."""
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be finite and positive")
        self._check_ready()
        try:
            self._check_receive_deadline()
            if self._startup:
                return self._startup.popleft()
            self._maybe_keepalive()
            deadline = time.monotonic() + timeout
            if self.receive_pending:
                deadline = min(deadline, self._receive_deadline)
            return self._read_message(deadline)
        except TimeoutError:
            self._check_receive_deadline()
            raise
        except (OSError, RuntimeError, ValueError) as exc:
            self.close()
            if isinstance(exc, QuiiConnectionError):
                raise
            raise QuiiConnectionError("LAN talk receive failed") from exc

    def _read_message(self, deadline: float) -> DecodedQuiiMessage:
        header = self._pending_header
        if header is None:
            header = decode_tcp_header(
                self._read_exact(32, deadline), crypto_mode=2, key=self._key
            )
            self._validate_header(header)
            self._pending_header = header
        payload = decode_tcp_payload(
            header,
            self._read_exact(header.read_size, deadline),
            crypto_mode=2,
            key=self._key,
        )
        self._pending_header = None
        self._check_receive_deadline()
        if not header.is_media:
            self._command(header, payload)
        message: DecodedQuiiMessage = {
            "header": header.header,
            "payload": payload,
            "is_media": header.is_media,
            "plausible": True,
        }
        if self._message_observer is not None:
            self._message_observer(message)
        return message

    def _validate_header(self, header: DecodedTcpHeader) -> None:
        if header.is_media:
            offset = header.header.flag16 | (header.header.flag17 << 8)
            if (
                not 0 < header.read_size <= MAX_MEDIA_BYTES
                or header.header.flag15 != 0
                or header.command_payload_size % 16
                or header.command_payload_size > header.read_size
                or offset > header.read_size
            ):
                raise QuiiConnectionError(
                    "unsupported or invalid LAN talk media header"
                )
        elif (
            header.header.packet_type not in {0, 0x0B, 0x0C, 0x0D}
            or not 32 <= header.read_size <= 4096
            or header.read_size % 16
        ):
            raise QuiiConnectionError("invalid LAN talk command header")

    def _command(self, header: DecodedTcpHeader, payload: bytes) -> None:
        raw = header.header.raw
        if not hmac.compare_digest(payload[:32], hashlib.sha256(raw).digest()):
            raise QuiiConnectionError("LAN talk command SHA256 check failed")
        kind = raw[0]
        status_key = {
            0x0B: "open_status",
            0x0C: "c_status",
            0x0D: "d_status",
        }.get(kind)
        if status_key is not None:
            self._handshake[status_key] = raw[11]
        if kind and raw[11]:
            raise QuiiConnectionError(
                f"LAN talk command 0x{kind:02x} rejected with status {raw[11]}"
            )
        if kind == 0x0B:
            if self.codec is not None:
                raise QuiiConnectionError("unexpected LAN talk Open reply")
            mask = int.from_bytes(raw[12:14], "little")
            self._handshake["codec_mask"] = mask
            if not mask & 3:
                raise QuiiConnectionError(
                    "LAN talk device advertises no supported G.711 codec"
                )
            self.codec = 4 if mask & 1 else 5
            self.full_packet = raw[14] != 0
        elif kind == 0x0D:
            if self._pending_receive is None:
                if not self.ready:
                    raise QuiiConnectionError(
                        "unexpected LAN talk ready reply"
                    )
                return
            self.receiving = self._pending_receive
            self._pending_receive = None
            self.ready = True

    def _maybe_keepalive(self) -> None:
        interval = self.config.live_keepalive_interval
        if interval and time.monotonic() - self._last_keepalive >= interval:
            packet = build_live_play_packet_from_body(
                b"",
                packet_type=0,
                play_param=0,
                crypto_mode=2,
                key=self._key,
                encrypt=True,
            )[2]
            self._send(
                packet, deadline=time.monotonic() + self.config.connect_timeout
            )
            self._last_keepalive = time.monotonic()

    def _check_receive_deadline(self) -> None:
        if self.receive_pending and time.monotonic() >= self._receive_deadline:
            self.close()
            raise QuiiConnectionError(
                "LAN talk receive request timed out; no retry attempted"
            )

    def _remaining(self, deadline: float) -> float:
        self._check_closed()
        value = deadline - time.monotonic()
        if value <= 0:
            raise TimeoutError("LAN talk I/O deadline exceeded")
        return value

    def _send(self, packet: bytes, *, deadline: float) -> None:
        self._transport.set_timeout(self._remaining(deadline))
        self._transport.send_all(packet)
        self._check_closed()

    def _read_exact(self, size: int, deadline: float) -> bytes:
        self._transport.set_timeout(self._remaining(deadline))
        data = self._transport.recv_exact(size)
        self._check_closed()
        return data

    def _check_closed(self) -> None:
        if self._closed.is_set():
            raise QuiiConnectionError(
                "LAN talk session is closed; create a new session"
            )

    def _check_ready(self) -> None:
        self._check_closed()
        if not self.ready:
            raise QuiiConnectionError("LAN talk session is not ready")

    def close(self) -> None:
        """Interrupt socket I/O and discard buffered media; idempotent."""
        self._closed.set()
        self.ready = False
        self._pending_receive = None
        self._pending_header = None
        self._startup.clear()
        self._transport.close()

    def __enter__(self) -> "LanTalkSession":
        """Open the owned transport once."""
        return self.open()

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        """Close without attempting another protocol exchange."""
        self.close()
