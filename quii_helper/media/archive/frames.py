"""Strict, bounded CPacket collection for one archived JPEG or H.264 clip."""

from dataclasses import dataclass, field
from statistics import median
from typing import Any

from quii_helper.media.audio.recording import AudioRecording
from quii_helper.media.cpacket import parse_cpacket_header
from quii_helper.media.cpacket.constants import CPACKET_HEADER_LEN
from quii_helper.media.cpacket.header import cpacket_timestamp_ms
from quii_helper.media.h264.merge.probe_analysis import find_annexb_start_codes
from quii_helper.support.errors import CameraCaptureError

MAX_ARCHIVE_VIDEO_FRAMES = 65536
MAX_ARCHIVE_NALS_PER_FRAME = 4096


def nal_units(data: bytes) -> list[bytes]:
    """Split existing Annex B NALs without altering their encoded contents."""
    if data.count(b"\x00\x00\x01") > MAX_ARCHIVE_NALS_PER_FRAME:
        raise CameraCaptureError(
            "archive video exceeds the per-frame NAL limit"
        )
    starts = find_annexb_start_codes(data)
    return [
        data[
            offset
            + prefix : starts[i + 1][0] if i + 1 < len(starts) else len(data)
        ]
        for i, (offset, prefix) in enumerate(starts)
        if offset + prefix
        < (starts[i + 1][0] if i + 1 < len(starts) else len(data))
    ]


@dataclass(frozen=True)
class ArchiveVideoFrame:
    """One native access unit with device-local time normalized only at mux."""

    data: bytes = field(repr=False)
    timestamp_ms: int
    keyframe: bool


class ArchiveMedia:
    """Keep complete frames within caller-owned transfer budgets."""

    def __init__(
        self, kind: str, max_bytes: int, frame_rate: int | None = None
    ) -> None:
        self.kind = kind
        self.max_bytes = max_bytes
        self.received_bytes = 0
        self.jpeg = bytearray()
        self.frames: list[ArchiveVideoFrame] = []
        self.audio = AudioRecording()
        self.sps = b""
        self.pps = b""
        self.width = self.height = 0
        self.frame_rate = (
            float(frame_rate)
            if isinstance(frame_rate, int)
            and not isinstance(frame_rate, bool)
            and 0 < frame_rate <= 1000
            else 0.0
        )
        self._header = bytearray()
        self._body = bytearray()
        self._info: dict[str, Any] | None = None
        self._pending = 0
        self._jpeg_offset = 0
        self._jpeg_in_scan = False
        self._jpeg_has_scan = False

    def feed(self, payload: bytes) -> None:
        """Assemble split/coalesced CPackets without searching inside payloads."""
        offset = 0
        while offset < len(payload):
            if self._info is None:
                size = min(
                    CPACKET_HEADER_LEN - len(self._header),
                    len(payload) - offset,
                )
                self._header.extend(payload[offset : offset + size])
                offset += size
                if len(self._header) < CPACKET_HEADER_LEN:
                    return
                self._info = parse_cpacket_header(
                    self._header, require_complete=False
                )
                if self._info is None:
                    raise CameraCaptureError(
                        "archive CPacket has an invalid length or header"
                    )
                self._pending = int(self._info["frame_len"])
                if self._pending > self.max_bytes - self.received_bytes:
                    raise CameraCaptureError("archive media exceeds max_bytes")
                self.received_bytes += self._pending
                self._header.clear()
            size = min(self._pending, len(payload) - offset)
            self._body.extend(payload[offset : offset + size])
            self._pending -= size
            offset += size
            if not self._pending:
                self._accept(self._info, bytes(self._body))
                self._body.clear()
                self._info = None

    def _accept(self, info: dict[str, Any], data: bytes) -> None:
        if self.kind == "picture":
            if info["frame_type"] != 4 or info["codec"] != 3:
                raise CameraCaptureError(
                    "archive contains an invalid or non-JPEG CPacket"
                )
            self.jpeg.extend(data)
            return
        if info["frame_type"] in {7, 8}:
            return  # Both native writers ignore these non-audio/video packets.
        if info["frame_tag"] == 0xE3:
            if not self.frames:
                return
            if (
                info["codec"] not in {4, 5}
                or info.get("sample_rate") != 8000
                or info.get("channels") != 1
            ):
                raise CameraCaptureError(
                    "archive video supports G.711 8000 Hz mono audio only"
                )
            self.audio.feed({**info, "bitstream": data})
            if self.audio.skipped_reason:
                raise CameraCaptureError(
                    "invalid archive video audio timing or format"
                )
            return
        if info["frame_type"] not in {0, 1, 9, 10} or not (
            info["codec"] == 1 or 0x10 <= info["codec"] <= 0x1F
        ):
            raise CameraCaptureError(
                "archive video supports H.264 CPackets only"
            )
        units = nal_units(data)
        for unit in units:
            field = (
                "sps"
                if unit[0] & 31 == 7
                else "pps" if unit[0] & 31 == 8 else ""
            )
            if field:
                previous = getattr(self, field)
                if self.frames and previous and unit != previous:
                    raise CameraCaptureError(
                        "archive video parameter sets changed during the clip"
                    )
                setattr(self, field, unit)
        if not any(unit[0] & 31 in {1, 5} for unit in units):
            return
        keyframe = any(unit[0] & 31 == 5 for unit in units)
        if not self.frames and not keyframe:
            return  # Native MP4 writer waits for its first keyframe.
        if len(self.frames) >= MAX_ARCHIVE_VIDEO_FRAMES:
            raise CameraCaptureError(
                "archive video exceeds the frame-count limit"
            )
        try:
            stamp = cpacket_timestamp_ms(info["frame_stamp"], info["frame_ms"])
        except ValueError as exc:
            raise CameraCaptureError(
                "invalid archive video timestamp"
            ) from exc
        if (
            self.frames
            and not 0 <= stamp - self.frames[-1].timestamp_ms <= 30000
        ):
            raise CameraCaptureError(
                "archive video timestamps are nonmonotonic or discontinuous"
            )
        dimensions = info["width"], info["height"]
        if min(dimensions) <= 0 or (
            self.frames and dimensions != (self.width, self.height)
        ):
            raise CameraCaptureError(
                "archive video dimensions are missing or changed"
            )
        self.width, self.height = dimensions
        self.frame_rate = float(info["fps"]) or self.frame_rate
        self.frames.append(ArchiveVideoFrame(data, stamp, keyframe))
        self.audio.start_video(info)

    def jpeg_complete(self) -> bool:
        """Find a structural EOI incrementally, without decoding the image.

        APP/COM payloads can contain FF D9; only markers outside their declared
        lengths end a JPEG. Entropy data also permits stuffing and restarts.
        """
        data = self.jpeg
        if not self._jpeg_offset:
            if len(data) < 2:
                return False
            if data[:2] != b"\xff\xd8":
                raise CameraCaptureError("archive JPEG is missing SOI")
            self._jpeg_offset = 2
        while self._jpeg_offset < len(data):
            offset = self._jpeg_offset
            if self._jpeg_in_scan:
                offset = data.find(b"\xff", offset)
                if offset < 0:
                    self._jpeg_offset = len(data)
                    return False
            elif data[offset] != 0xFF:
                raise CameraCaptureError("archive JPEG has an invalid marker")
            while offset + 1 < len(data) and data[offset + 1] == 0xFF:
                offset += 1
            self._jpeg_offset = offset
            if offset + 1 == len(data):
                return False
            marker = data[offset + 1]
            if self._jpeg_in_scan and (marker == 0 or 0xD0 <= marker <= 0xD7):
                self._jpeg_offset = offset + 2
                continue
            if marker == 0xD9:
                if not self._jpeg_has_scan or offset + 2 != len(data):
                    raise CameraCaptureError(
                        "archive JPEG has no scan or has trailing data"
                    )
                return True
            if marker == 0x01:
                self._jpeg_offset = offset + 2
                continue
            if marker in {0, 0xD8} or 0xD0 <= marker <= 0xD7:
                raise CameraCaptureError("archive JPEG has an invalid marker")
            if offset + 4 > len(data):
                return False
            size = (data[offset + 2] << 8) | data[offset + 3]
            if size < 2:
                raise CameraCaptureError("archive JPEG has an invalid segment")
            end = offset + 2 + size
            if end > len(data):
                return False
            self._jpeg_in_scan = marker == 0xDA or (
                self._jpeg_in_scan and marker == 0xDC
            )
            self._jpeg_has_scan |= marker == 0xDA
            self._jpeg_offset = end
        return False

    def finish(self) -> None:
        """Validate framing after the selected protocol's end condition."""
        if self._info is not None or self._header:
            raise CameraCaptureError(
                "archive ended with an incomplete media CPacket"
            )
        if self.kind == "picture":
            if not self.jpeg.startswith(b"\xff\xd8") or not self.jpeg.endswith(
                b"\xff\xd9"
            ):
                raise CameraCaptureError(
                    "archive ended without a complete JPEG"
                )
        elif not self.frames or len(self.sps) < 4 or not self.pps:
            raise CameraCaptureError(
                "archive ended without decodable H.264 video"
            )
        else:
            self.last_duration_ms()
            if (
                self.audio.data
                and self.audio.offset_seconds >= self.duration_seconds
            ):
                raise CameraCaptureError(
                    "archive audio starts after video ends"
                )

    def last_duration_ms(self) -> int:
        """Infer only the final sample duration, never a requested clip length."""
        if self.frame_rate > 0:
            return max(1, round(1000 / self.frame_rate))
        intervals = [
            b.timestamp_ms - a.timestamp_ms
            for a, b in zip(self.frames, self.frames[1:])
            if b.timestamp_ms > a.timestamp_ms
        ]
        if intervals:
            return int(median(intervals))
        raise CameraCaptureError(
            "archive video requires a known FPS or a positive frame interval"
        )

    @property
    def duration_seconds(self) -> float:
        """Original normalized video timeline, including its final sample."""
        return (
            self.frames[-1].timestamp_ms
            - self.frames[0].timestamp_ms
            + self.last_duration_ms()
        ) / 1000
