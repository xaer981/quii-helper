"""Bounded archive download; never opens live preview or cloud fallback."""

import hashlib
import hmac
import math
import time
from pathlib import Path

from quii_helper.config import AutonomousConfig
from quii_helper.device.cgi.models import DeviceRecordFileInfo
from quii_helper.device.security.auth import encode_device_password
from quii_helper.media.archive.frames import ArchiveMedia
from quii_helper.media.archive.video import render_archive_mp4, require_ffmpeg
from quii_helper.protocols.tcp.archive.packets import (
    keepalive_packet,
    open_packet,
    open_packet_dynamic,
    playback_mode_packet,
    record_descriptor,
    seek_packet,
    setup_packet,
    start_transfer_packet,
)
from quii_helper.protocols.tcp.codec.message_codec import (
    DecodedTcpHeader,
    decode_tcp_header,
    decode_tcp_payload,
)
from quii_helper.protocols.tcp.live.session import (
    COMMAND_TYPES,
    MAX_TCP_PAYLOAD_BYTES,
    PLAY_REPLY_TYPES,
    validate_lan_config,
)
from quii_helper.protocols.tcp.transport.client import TcpTransportFactory
from quii_helper.protocols.tcp.transport.socket_transport import (
    TcpSocketTransport,
)
from quii_helper.support.errors import (
    CameraCaptureError,
    ConfigurationError,
    QuiiConnectionError,
)


def download_record_bytes(
    config: AutonomousConfig,
    entry: DeviceRecordFileInfo,
    *,
    timeout: float = 30.0,
    max_bytes: int = 16 * 1024 * 1024,
    temporary_directory: Path = Path("data"),
    transport_factory: TcpTransportFactory = TcpSocketTransport,
    protocol: str = "default",
) -> bytes:
    """Return JPEG or MP4 bytes via LAN file mode, with bounded time/memory.

    Video uses private temporary files, removed on success and failure.
    There is no cloud fallback, device-setting change or retry. The configured
    host/port are authoritative; entry.url is ignored.
    """
    try:
        valid_timeout = (
            not isinstance(timeout, bool)
            and isinstance(timeout, (int, float))
            and math.isfinite(timeout)
            and timeout > 0
        )
    except OverflowError:
        valid_timeout = False
    if not valid_timeout:
        raise ConfigurationError("archive timeout must be finite and positive")
    if (
        isinstance(max_bytes, bool)
        or not isinstance(max_bytes, int)
        or max_bytes <= 0
    ):
        raise ConfigurationError(
            "archive max_bytes must be a positive integer"
        )
    if protocol not in ("default", "pipelined"):
        raise ConfigurationError(
            "archive protocol must be 'default' or 'pipelined'"
        )
    validate_lan_config(config)
    record = record_descriptor(entry)
    executable = require_ffmpeg() if entry.file_type == "video" else ""
    key = config.stream_key.encode("utf-8")
    pipelined = protocol == "pipelined"
    if pipelined:
        if not config.dynamic_password:
            raise ConfigurationError(
                "protocol='pipelined' requires config.dynamic_password"
            )
        initial = open_packet_dynamic(
            record, config.dynamic_password, config.oem, key
        )
    else:
        initial = open_packet(
            record, encode_device_password(config.auth_code), key
        )
    media = ArchiveMedia(entry.file_type, max_bytes, entry.frame_rate)
    transfer = _ArchiveDownload(config, key, timeout, transport_factory)
    try:
        transfer.connect()
        transfer.send(initial)
        if pipelined:
            # This firmware is silent to a bare Open: send the whole sequence
            # up front, then read (verified on Intelbras Allo wT7).
            transfer.send(seek_packet(record, key))
            transfer.send(playback_mode_packet(key))
            transfer.send(start_transfer_packet(key))
        opened = pipelined
        while True:
            if opened:
                transfer.keepalive()
            try:
                header, payload = transfer.receive()
            except TimeoutError:
                transfer.remaining()
                continue
            if header.is_media:
                if not opened:
                    raise QuiiConnectionError(
                        "archive media arrived before Open reply"
                    )
                media.feed(payload)
                if (
                    pipelined
                    and entry.file_type == "picture"
                    and bytes(media.jpeg).rstrip(b"\x00").endswith(b"\xff\xd9")
                ):
                    # Pipelined firmware may not send a final command frame;
                    # stop once the JPEG is complete (EOI received).
                    media.finish()
                    break
                continue
            raw = header.header.raw
            kind = raw[0]
            # Native pending Open state processes the first authenticated reply.
            if not opened:
                if raw[11]:
                    raise QuiiConnectionError(
                        f"archive Open rejected with status {raw[11]}"
                    )
                opened = True
                transfer.send(seek_packet(record, key))
                transfer.send(playback_mode_packet(key))
            elif kind == 8:
                media.finish()
                break
            elif kind in {2, 3, 5} | PLAY_REPLY_TYPES and raw[11]:
                raise QuiiConnectionError(
                    f"archive command 0x{kind:02x} rejected with status {raw[11]}"
                )
    except (OSError, RuntimeError, ValueError) as exc:
        if isinstance(exc, (CameraCaptureError, QuiiConnectionError)):
            raise
        raise QuiiConnectionError(
            "archive media transfer failed; no cloud fallback attempted"
        ) from exc
    finally:
        transfer.close()
    transfer.remaining()
    if entry.file_type == "picture":
        result = bytes(media.jpeg)
        transfer.remaining()
        return result
    return render_archive_mp4(
        media,
        directory=temporary_directory,
        executable=executable,
        deadline=transfer.deadline,
        max_bytes=max_bytes,
    )


class _ArchiveDownload:
    """Single-owner transport; partial reads survive socket timeouts."""

    def __init__(
        self,
        config: AutonomousConfig,
        key: bytes,
        timeout: float,
        transport_factory: TcpTransportFactory,
    ) -> None:
        self.config = config
        self.key = key
        self.deadline = time.monotonic() + timeout
        self.transport = transport_factory(
            config.device_host, config.stream_port
        )
        self.pending: DecodedTcpHeader | None = None
        self.last_keepalive = time.monotonic()

    def remaining(self) -> float:
        value = self.deadline - time.monotonic()
        if value <= 0:
            raise CameraCaptureError(
                "archive media download timed out before complete transfer"
            )
        return value

    def send(self, packet: bytes) -> None:
        self.transport.set_timeout(self.remaining())
        self.transport.send_all(packet)

    def _read(self, size: int) -> bytes:
        self.transport.set_timeout(min(1.0, self.remaining()))
        data = self.transport.recv_exact(size)
        self.remaining()
        return data

    def connect(self) -> None:
        self.transport.connect(
            timeout=min(self.config.connect_timeout, self.remaining())
        )
        self.send(setup_packet())
        while True:
            try:
                raw = self._read(32)
                break
            except TimeoutError:
                self.remaining()
        if raw[0] != 0xA9 or raw[9] != 0:
            raise QuiiConnectionError("archive TCP setup rejected")
        if raw[10:12] != b"\x02\x01":
            raise QuiiConnectionError("archive media requires AES-256/SHA256")

    def receive(self) -> tuple[DecodedTcpHeader, bytes]:
        header = self.pending
        if header is None:
            header = decode_tcp_header(
                self._read(32), crypto_mode=2, key=self.key
            )
            self._validate_header(header)
            self.pending = header
        payload = decode_tcp_payload(
            header, self._read(header.read_size), crypto_mode=2, key=self.key
        )
        self.pending = None
        if not header.is_media:
            size = (
                header.header.raw_size
                if header.header.packet_type == 0xFE
                else 0
            )
            digest = hashlib.sha256(
                header.header.raw + payload[:size]
            ).digest()
            if size + 32 > len(payload) or not hmac.compare_digest(
                payload[size : size + 32], digest
            ):
                raise QuiiConnectionError(
                    "archive command SHA256 check failed"
                )
        return header, payload

    def _validate_header(self, header: DecodedTcpHeader) -> None:
        if header.is_media:
            offset = header.header.flag16 | (header.header.flag17 << 8)
            if (
                not 0 < header.read_size <= MAX_TCP_PAYLOAD_BYTES
                or header.header.flag15 != 0
                or header.command_payload_size % 16
                or header.command_payload_size > header.read_size
                or offset > header.read_size
            ):
                raise QuiiConnectionError(
                    "unsupported or invalid archive media header"
                )
        elif (
            header.header.packet_type not in COMMAND_TYPES | {2, 3}
            or not 32 <= header.read_size <= 4096
            or header.read_size % 16
        ):
            raise QuiiConnectionError("invalid archive command header")

    def keepalive(self) -> None:
        interval = self.config.live_keepalive_interval
        if interval and time.monotonic() - self.last_keepalive >= interval:
            self.send(keepalive_packet(self.key))
            self.last_keepalive = time.monotonic()

    def close(self) -> None:
        self.transport.close()
