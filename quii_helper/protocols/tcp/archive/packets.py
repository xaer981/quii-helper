"""CQUIIStreamFile layouts checked in vHome and vEye Pro native code."""

import hashlib
import re
import struct
import time
from dataclasses import dataclass
from datetime import datetime

from quii_helper.device.cgi.models import DeviceRecordFileInfo
from quii_helper.protocols.quii.crypto import (
    aes_cbc_crypt,
    compute_ext_data_len,
)
from quii_helper.support.errors import ConfigurationError

_DATE = r"([0-9]{1,4})-([0-9]{1,2})-([0-9]{1,2})-([0-9]{1,2})-([0-9]{1,2})-([0-9]{1,2})"
_FILENAME = re.compile(
    r"([0-9]{1,5})_"
    + _DATE
    + "_"
    + _DATE
    + r"_(-?[0-9]{1,10})" * 7
    + r"(?:\.[a-z0-9]{1,8})?",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RecordDescriptor:
    """Validated file selectors; no credentials, URL or filesystem pathname."""

    file_info: bytes
    start_stamp: int


def _packed_time(values: list[int]) -> int:
    try:
        year, month, day, hour, minute, second = values
        value = datetime(year, month, day, hour, minute, second)
        if not 2000 <= value.year <= 2063:
            raise ValueError
    except ValueError:
        raise ConfigurationError(
            "archive record has an invalid device-local time"
        ) from None
    return (
        ((year - 2000) << 26)
        | (month << 22)
        | (day << 17)
        | (hour << 12)
        | (minute << 6)
        | second
    )


def record_descriptor(entry: DeviceRecordFileInfo) -> RecordDescriptor:
    """Read native filename fields and `idx`, without guessing from CGI ids.

    Filename channel/time/flags are authoritative in native FillFileInfo.
    CGI `filesize` is not a byte count and must not determine JPEG completeness.
    """
    if not isinstance(entry, DeviceRecordFileInfo):
        raise ConfigurationError("entry must be a CameraDeviceRecordFileInfo")
    if entry.file_type not in {"picture", "video"}:
        raise ConfigurationError(
            "download_record requires an archived picture or video entry"
        )
    if not isinstance(entry.file_name, str) or len(entry.file_name) > 512:
        raise ConfigurationError("archive record requires a native filename")
    name = entry.file_name.replace("\n", "")
    match = _FILENAME.fullmatch(name)
    if match is None:
        raise ConfigurationError(
            "unsupported archive filename; expected native 20-field format"
        )
    fields = [int(value) for value in match.groups()]
    if fields[0] > 65535 or any(
        not -0x80000000 <= value <= 0xFFFFFFFF for value in fields[13:]
    ):
        raise ConfigurationError("archive filename field exceeds native range")
    picture = entry.file_type == "picture"
    index = entry.picture_index
    if picture and (
        not isinstance(index, str)
        or not re.fullmatch(r"[0-9]{1,10}", index)
        or int(index) > 0xFFFFFFFF
    ):
        raise ConfigurationError(
            "archive picture requires a valid uint32 picture_index (idx)"
        )
    stamp = _packed_time(fields[1:7])
    seek_stamp = stamp
    if not isinstance(entry.start_time, str):
        raise ConfigurationError(
            "archive start_time must be a calendar string"
        )
    if entry.start_time:
        start_match = re.fullmatch(
            r"([0-9]{4})-([0-9]{2})-([0-9]{2})[tT ]"
            r"([0-9]{2}):([0-9]{2}):([0-9]{2})[zZ]?",
            entry.start_time,
        )
        if start_match is None:
            raise ConfigurationError(
                "unsupported archive start_time; expected device-local calendar time"
            )
        seek_stamp = _packed_time(
            [int(value) for value in start_match.groups()]
        )
    info = bytearray(19)
    struct.pack_into("<HI", info, 0, fields[0], stamp)
    info[6] = fields[13] & 255
    struct.pack_into("<I", info, 7, fields[15] & 0xFFFFFFFF)
    info[11:15] = bytes(
        (
            fields[17] & 255,
            fields[16] & 255,
            fields[14] & 255,
            (fields[18] >> 5) & 1,
        )
    )
    # ParseURL overwrites the initial rec/pic flag; rec leaves idx zeroed.
    if fields[17]:
        tail = int(index) if picture else 0
    else:
        tail = _packed_time(fields[7:13])
        if tail < stamp:
            raise ConfigurationError("archive end time precedes start time")
    struct.pack_into("<I", info, 15, tail)
    return RecordDescriptor(bytes(info), seek_stamp)


def setup_packet() -> bytes:
    """Build file SendSetup: unlike live/talk, byte 9 is 1."""
    header = bytearray(32)
    header[0], header[9] = 0xA9, 1
    return bytes(header)


def _header(kind: int) -> bytearray:
    header = bytearray(32)
    header[0] = kind
    struct.pack_into("<QH", header, 1, int(time.time()), 32)
    return header


def _seal(header: bytearray, key: bytes, body: bytes = b"") -> bytes:
    _, size = compute_ext_data_len(len(body), crypto_mode=2)
    struct.pack_into("<H", header, 9, size)
    extension = (body + hashlib.sha256(header + body).digest()).ljust(
        size, b"\0"
    )
    return aes_cbc_crypt(bytes(header), key, crypto_mode=2) + aes_cbc_crypt(
        extension, key, crypto_mode=2
    )


def open_packet(record: RecordDescriptor, password: str, key: bytes) -> bytes:
    """Filename Open (0x02), with empty native custom id, AES-256/SHA256."""
    body = b"adminapp2&&" + password.encode("utf-8") + b"\0\0"
    if len(body) + 32 > 65520:
        raise ConfigurationError(
            "archive authentication body exceeds native range"
        )
    header = _header(2)
    struct.pack_into("<H", header, 11, len(body))
    header[13:32] = record.file_info
    return _seal(header, key, body)


def seek_packet(record: RecordDescriptor, key: bytes) -> bytes:
    """Start at the file's calendar time, matching the download reader's Seek."""
    header = _header(5)
    struct.pack_into("<I", header, 11, record.start_stamp)
    return _seal(header, key)


def playback_mode_packet(key: bytes) -> bytes:
    """Select native session-local normal playback mode/speed (1/1)."""
    header = _header(0x15)
    header[29:31] = b"\x01\x01"
    return _seal(header, key)


def keepalive_packet(key: bytes) -> bytes:
    """Build a header-only native keepalive without live-play flags."""
    return _seal(_header(0), key)
