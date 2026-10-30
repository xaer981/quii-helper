"""Direct-IP QUII session with supplied credentials and no cloud dependency."""

import hashlib
import hmac
import ipaddress
import math
import time
import warnings
from threading import Event
from typing import cast

from quii_helper.config import AutonomousConfig
from quii_helper.config.connection import validate_connection_options
from quii_helper.device.security.auth import encode_device_password
from quii_helper.device.security.streamkey import validate_stream_credentials
from quii_helper.models.packets import DecodedQuiiMessage
from quii_helper.protocols.quii.live_envelope import (
    build_live_play_packet_from_body,
)
from quii_helper.protocols.tcp.codec.message_codec import (
    DecodedTcpHeader,
    decode_tcp_header,
    decode_tcp_payload,
)
from quii_helper.protocols.tcp.live.packet_builder import (
    build_stream_switch_packet,
    validate_live_identity,
)
from quii_helper.protocols.tcp.live.transparent import (
    build_readonly_device_query,
)
from quii_helper.protocols.tcp.transport.client import (
    QuiiClient,
    TcpTransportFactory,
)
from quii_helper.protocols.tcp.transport.socket_transport import (
    TcpSocketTransport,
)
from quii_helper.support.errors import ConfigurationError, QuiiConnectionError

MAX_TCP_PAYLOAD_BYTES = 5 * 1024 * 1024
COMMAND_TYPES = {0, 1, 5, 6, 7, 8, 9, 10, 12, 13, 14, 15, 17, 0xAA, 0xFE}
PLAY_REPLY_TYPES = {1, 12, 13, 17, 0xAA}


def validate_lan_config(config: AutonomousConfig) -> None:
    """Validate only LAN playback inputs; never read assets or resolve hosts."""
    if config.connection_mode != "lan":
        raise ConfigurationError(
            "direct TCP playback requires connection_mode='lan'"
        )
    validate_connection_options(config.connection_mode, config.stream_port)
    for name, expected in (
        ("live_play_payload", "path"),
        ("live_inner", False),
        ("live_newcn", False),
    ):
        if getattr(config, name) != expected:
            # A stable warning location avoids duplicate RTSP preflight warnings.
            warnings.warn(
                f"{name} is ignored in LAN playback; using {name}={expected!r}. "
                "Non-default live options apply only to the cloud preview path.",
                UserWarning,
            )
    try:
        address = ipaddress.ip_address(config.device_host)
    except ValueError:
        raise ConfigurationError(
            "LAN playback requires an explicit device_host IP address"
        ) from None
    if address.is_unspecified or address.is_multicast:
        raise ConfigurationError(
            "LAN playback requires a unicast device_host IP address"
        )
    validate_stream_credentials(config.stream_key, config.auth_code)
    for name in ("channel", "stream"):
        value = getattr(config, name)
        maximum = 0xFFFF if name == "channel" else 0x100
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or not 1 <= value <= maximum
        ):
            raise ConfigurationError(
                f"{name} must be an integer between 1 and {maximum}"
            )
    if (
        not math.isfinite(config.connect_timeout)
        or config.connect_timeout <= 0
    ):
        raise ConfigurationError("connect_timeout must be finite and positive")
    if (
        not math.isfinite(config.live_keepalive_interval)
        or config.live_keepalive_interval < 0
    ):
        raise ConfigurationError(
            "live_keepalive_interval must be finite and nonnegative"
        )


class LanTcpSession:
    """Own one TCP socket and yield decrypted messages for later media assembly.

    Only the native-checked AES-256/SHA256 profile with unencrypted media is
    supported initially. Other profiles fail closed rather than guessing keys.
    The caller supplies AUTH_CODE (raw or encoded) and the saved 32-byte key.
    No credentials are loaded, renewed or persisted by this class.
    Send and receive operations have one owner thread; only close() may run
    concurrently. Stream switches are explicit and never sent during open().
    The handshake/client_id options are internal diagnostics only; Camera
    retains setup_path and never selects or falls back to another handshake.
    """

    def __init__(
        self,
        config: AutonomousConfig,
        *,
        transport_factory: TcpTransportFactory = TcpSocketTransport,
        handshake: str = "setup_path",
        client_id: str = "",
    ) -> None:
        validate_lan_config(config)
        if handshake not in ("setup_path", "setup_oem", "fast_oem"):
            raise ConfigurationError("unsupported LAN diagnostic handshake")
        custom_id = None
        if handshake != "setup_path":
            if not isinstance(config.oem, str):
                raise ConfigurationError("diagnostic OEM must be a string")
            # QvCore.initParams removes commas before native SetCustomID.
            custom_id = config.oem.replace(",", "")
        try:
            validate_live_identity(custom_id, client_id)
        except ValueError as exc:
            raise ConfigurationError(str(exc)) from None
        self.config = config
        self._handshake = handshake
        self._custom_id = custom_id
        self._client_id = client_id
        self._key = config.stream_key.encode("utf-8")
        self._client = QuiiClient(
            config.device_host,
            config.stream_port,
            "adminapp2",
            encode_device_password(config.auth_code),
            f"/mode=real&idc={config.channel}&ids={config.stream}&ap=2",
            config.stream_key,
            transport_factory=transport_factory,
        )
        self._pending_header: DecodedTcpHeader | None = None
        self._opened = False
        self.play_accepted = False
        self.active_stream: int | None = None
        self._pending_stream: int | None = None
        self._switch_deadline: float | None = None
        self._last_keepalive = 0.0
        self._closed = Event()

    def open(self) -> "LanTcpSession":
        """Connect, validate setup and send play; close on every startup failure."""
        if self._opened:
            return self
        if self._closed.is_set():
            raise QuiiConnectionError(
                "LAN TCP session is closed; create a new session to reconnect"
            )
        try:
            self._client.connect(timeout=self.config.connect_timeout)
            self._check_cancelled()
            if self._handshake == "fast_oem":
                self._client.crypto_mode = 2
            else:
                self._client.send_setup()
                setup = self._client.recv_setup()
                self._check_cancelled()
                raw = cast(bytes, setup["raw"])
                if raw[0] != 0xA9 or setup["status"] != 0:
                    raise QuiiConnectionError("LAN TCP setup was rejected")
                if setup["crypto_mode"] != 2 or raw[11] != 1:
                    raise QuiiConnectionError(
                        "unsupported LAN TCP crypto/SHA profile; AES-256/SHA256 required"
                    )
            if self._handshake == "setup_path":
                self._client.send_live_open()
            else:
                packet = self._client.live_open_builder.build_live_open_packet(
                    crypto_mode=2,
                    custom_id=self._custom_id,
                    client_id=self._client_id,
                    fast_play=self._handshake == "fast_oem",
                )
                self._client.transport.send_all(packet)
            self._opened = True
            self._last_keepalive = time.monotonic()
            self._check_cancelled()
            return self
        except BaseException as exc:
            self.close()
            if isinstance(
                exc, (OSError, RuntimeError, ValueError)
            ) and not isinstance(exc, QuiiConnectionError):
                raise QuiiConnectionError(
                    "LAN TCP startup failed; no cloud fallback attempted"
                ) from exc
            raise

    @property
    def stream_switch_pending(self) -> bool:
        """Whether an explicit switch still awaits its authenticated reply."""
        return self._pending_stream is not None

    def request_device_query(self, command: int) -> None:
        """Send one internal diagnostic query (5/6/2/14) on an accepted play.

        This does not wait for a reply, retry or send a generic transparent ACK.
        The caller owns query ordering and bounded observation via recv_message.
        Camera never calls this automatically; write commands are rejected.
        """
        packet = build_readonly_device_query(
            command,
            key=self._key,
            channel=self.config.channel if command == 14 else None,
        )
        if not self._opened or not self.play_accepted:
            raise QuiiConnectionError("LAN TCP play is not active")
        try:
            self._client.transport.set_timeout(self.config.connect_timeout)
            self._client.transport.send_all(packet)
            self._check_cancelled()
        except BaseException as exc:
            self.close()
            if isinstance(exc, (OSError, RuntimeError)) and not isinstance(
                exc, QuiiConnectionError
            ):
                raise QuiiConnectionError(
                    "LAN TCP device query send failed; no retry attempted"
                ) from exc
            raise

    def request_stream_switch(
        self, stream: int, *, timeout: float | None = 5.0
    ) -> None:
        """Send an internal, opt-in switch without consuming any media.

        Args:
            stream: One-based selector; requesting the current one is allowed.
            timeout: Positive finite deadline covering send and acknowledgement.
                None disables only the ACK deadline for bounded diagnostics;
                sending still uses connect_timeout.

        Continue calling recv_message() on the same thread to process the reply
        and enforce the deadline. Success updates active_stream, not config.
        Acknowledgement alone does not prove the encoded resolution changed.
        Rejection, expiry or send failure closes the session; no retry/fallback
        is attempted. A second request cannot overlap an outstanding one.
        With no ACK deadline, the caller must bound observation and close the
        session; a missing reply never implies success or permits another switch.
        """
        packet = build_stream_switch_packet(stream, key=self._key)
        if timeout is not None and (
            not math.isfinite(timeout) or timeout <= 0
        ):
            raise ValueError("timeout must be finite and positive")
        if not self._opened or not self.play_accepted:
            raise QuiiConnectionError("LAN TCP play is not active")
        self._check_switch_timeout()
        if self.stream_switch_pending:
            raise QuiiConnectionError("a LAN TCP stream switch is pending")
        self._pending_stream = stream
        self._switch_deadline = (
            time.monotonic() + timeout if timeout is not None else None
        )
        try:
            self._client.transport.set_timeout(
                self.config.connect_timeout if timeout is None else timeout
            )
            self._client.transport.send_all(packet)
            self._check_cancelled()
            self._check_switch_timeout()
        except BaseException as exc:
            self.close()
            if isinstance(exc, (OSError, RuntimeError)) and not isinstance(
                exc, QuiiConnectionError
            ):
                raise QuiiConnectionError(
                    "LAN TCP stream switch send failed; no retry attempted"
                ) from exc
            raise

    def recv_message(self, *, timeout: float = 1.0) -> DecodedQuiiMessage:
        """Read one bounded message, preserving header/body state on timeouts.

        A TimeoutError permits another read on the same session. Invalid data,
        rejected play, EOF or other receive errors close the session instead.
        """
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be finite and positive")
        if not self._opened:
            raise QuiiConnectionError("LAN TCP session is not open")
        deadline = time.monotonic() + timeout
        try:
            self._check_switch_timeout()
            if self._switch_deadline is not None:
                deadline = min(deadline, self._switch_deadline)
            self._maybe_send_keepalive()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("LAN TCP message read timed out")
            self._client.transport.set_timeout(remaining)
            header = self._pending_header
            if header is None:
                header = decode_tcp_header(
                    self._client.recv_exact(32), crypto_mode=2, key=self._key
                )
                self._validate_header(header)
                self._pending_header = header
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("LAN TCP message read timed out")
            self._client.transport.set_timeout(remaining)
            raw = self._client.recv_exact(header.read_size)
            self._check_cancelled()
            payload = decode_tcp_payload(
                header, raw, crypto_mode=2, key=self._key
            )
            self._pending_header = None
            self._check_switch_timeout()
            if not header.is_media:
                self._check_command(header, payload)
            return {
                "header": header.header,
                "payload": payload,
                "is_media": header.is_media,
                "plausible": True,
            }
        except TimeoutError:
            self._check_switch_timeout()
            raise
        except (OSError, ValueError, RuntimeError) as exc:
            self.close()
            if isinstance(exc, QuiiConnectionError):
                raise
            raise QuiiConnectionError(
                "LAN TCP receive failed; no cloud fallback attempted"
            ) from exc

    def _validate_header(self, header: DecodedTcpHeader) -> None:
        if (
            header.header.packet_type not in COMMAND_TYPES
            and not header.is_media
        ):
            raise QuiiConnectionError(
                "invalid LAN TCP packet type (check saved credentials)"
            )
        if not 0 < header.read_size <= MAX_TCP_PAYLOAD_BYTES:
            raise QuiiConnectionError("invalid LAN TCP payload length")
        if header.is_media:
            if header.header.flag15 != 0:
                raise QuiiConnectionError(
                    "separate media encryption is not supported by this LAN profile"
                )
            if (
                header.command_payload_size % 16
                or header.command_payload_size > header.read_size
            ):
                raise QuiiConnectionError(
                    "invalid LAN TCP encrypted prefix length"
                )
            offset = header.header.flag16 | (header.header.flag17 << 8)
            if offset > header.read_size:
                raise QuiiConnectionError("invalid LAN TCP media offset")
        elif header.read_size % 16 or header.read_size < 32:
            raise QuiiConnectionError(
                "invalid LAN TCP encrypted command length"
            )

    def _check_command(self, header: DecodedTcpHeader, payload: bytes) -> None:
        # Native OnRecvCommand hashes the body only for transparent type 0xfe.
        size = (
            header.header.raw_size if header.header.packet_type == 0xFE else 0
        )
        digest = hashlib.sha256(header.header.raw + payload[:size]).digest()
        if size + 32 > len(payload) or not hmac.compare_digest(
            payload[size : size + 32], digest
        ):
            raise QuiiConnectionError("LAN TCP command SHA256 check failed")
        if header.header.packet_type in PLAY_REPLY_TYPES:
            if header.header.raw[11] != 0:
                raise QuiiConnectionError(
                    f"LAN TCP play rejected with status {header.header.raw[11]}"
                )
            self.play_accepted = header.header.raw[12] == 1
            if self.play_accepted and self.active_stream is None:
                self.active_stream = self.config.stream
        if header.header.packet_type == 9 and self.stream_switch_pending:
            status = header.header.raw[11]
            if status != 0:
                raise QuiiConnectionError(
                    f"LAN TCP stream switch rejected with status {status}"
                )
            self.active_stream = self._pending_stream
            self._pending_stream = None
            self._switch_deadline = None

    def _check_switch_timeout(self) -> None:
        if (
            self._switch_deadline is not None
            and time.monotonic() >= self._switch_deadline
        ):
            # There is no switch request id: close rather than misread a late ACK.
            self.close()
            raise QuiiConnectionError("LAN TCP stream switch timed out")

    def _maybe_send_keepalive(self) -> None:
        interval = self.config.live_keepalive_interval
        now = time.monotonic()
        if (
            not self.play_accepted
            or interval == 0
            or now - self._last_keepalive < interval
        ):
            return
        # Native SendKeepAlive leaves all play flags zero.
        _, _, packet = build_live_play_packet_from_body(
            b"",
            packet_type=0,
            play_param=0,
            crypto_mode=2,
            key=self._key,
            encrypt=True,
        )
        self._client.transport.send_all(packet)
        self._last_keepalive = now

    def close(self) -> None:
        """Release the socket; safe after failure, cancellation or repeated calls."""
        self._closed.set()
        self._opened = False
        self.play_accepted = False
        self.active_stream = None
        self._pending_stream = None
        self._switch_deadline = None
        self._pending_header = None
        self._client.close()

    def _check_cancelled(self) -> None:
        if self._closed.is_set():
            raise QuiiConnectionError("LAN TCP session was closed during I/O")

    def __enter__(self) -> "LanTcpSession":
        return self.open()

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()
