"""Preserve archive CPacket timestamps while remuxing H.264 to MP4."""

import shutil
import struct
import subprocess
import time
from pathlib import Path
from tempfile import TemporaryDirectory

from quii_helper.media.archive.frames import ArchiveMedia, nal_units
from quii_helper.media.h264.io.ffmpeg_state import h264_mp4_command
from quii_helper.support.errors import CameraCaptureError, MediaRenderError


def require_ffmpeg() -> str:
    """Preflight before opening the camera; JPEG downloads do not need FFmpeg."""
    executable = shutil.which("ffmpeg")
    if executable is None:
        raise MediaRenderError(
            "archive video requires FFmpeg on PATH; install FFmpeg and check 'ffmpeg -version'"
        )
    return executable


def remaining(deadline: float) -> float:
    value = deadline - time.monotonic()
    if value <= 0:
        raise CameraCaptureError(
            "archive download timed out before complete transfer/export"
        )
    return value


def _unsigned(value: int) -> bytes:
    return value.to_bytes(max(1, (value.bit_length() + 7) // 8), "big")


def _element(tag: int, body: bytes) -> bytes:
    # EBML finite sizes reserve the all-one value for unknown length.
    size = max(1, (len(body).bit_length() + 6) // 7)
    if len(body) == (1 << (7 * size)) - 1:
        size += 1
    length = (len(body) | (1 << (7 * size))).to_bytes(size, "big")
    return _unsigned(tag) + length + body


def _uint(tag: int, value: int) -> bytes:
    return _element(tag, _unsigned(value))


def _write_timed_video(
    path: Path, media: ArchiveMedia, deadline: float
) -> None:
    """Use one private Matroska intermediate, not one file per access unit.

    AVC CodecPrivate and length-prefixed NALs follow the Matroska AVC mapping.
    Each cluster has its original relative timestamp; no CFR retiming occurs.
    """
    sps, pps = media.sps, media.pps
    if max(len(sps), len(pps)) > 65535:
        raise MediaRenderError("archive H.264 parameter set exceeds AVC range")
    avcc = (
        b"\x01"
        + sps[1:4]
        + b"\xff\xe1"
        + struct.pack(">H", len(sps))
        + sps
        + b"\x01"
        + struct.pack(">H", len(pps))
        + pps
    )
    header = _element(
        0x1A45DFA3,
        _uint(0x4286, 1)
        + _uint(0x42F7, 1)
        + _uint(0x42F2, 4)
        + _uint(0x42F3, 8)
        + _element(0x4282, b"matroska")
        + _uint(0x4287, 4)
        + _uint(0x4285, 2),
    )
    info = _element(
        0x1549A966,
        _uint(0x2AD7B1, 1000000)
        + _element(0x4D80, b"quii-helper")
        + _element(0x5741, b"quii-helper")
        + _element(0x4489, struct.pack(">d", media.duration_seconds * 1000)),
    )
    track = _element(
        0x1654AE6B,
        _element(
            0xAE,
            _uint(0xD7, 1)
            + _uint(0x73C5, 1)
            + _uint(0x83, 1)
            + _element(0x86, b"V_MPEG4/ISO/AVC")
            + _element(0x63A2, avcc)
            + _uint(0x23E383, media.last_duration_ms() * 1000000)
            + _element(
                0xE0, _uint(0xB0, media.width) + _uint(0xBA, media.height)
            ),
        ),
    )
    with path.open("wb") as output:
        output.write(
            header
            + b"\x18\x53\x80\x67\x01\xff\xff\xff\xff\xff\xff\xff"
            + info
            + track
        )
        origin = media.frames[0].timestamp_ms
        for frame in media.frames:
            remaining(deadline)
            payload = b"".join(
                struct.pack(">I", len(unit)) + unit
                for unit in nal_units(frame.data)
            )
            block = (
                b"\x81\x00\x00"
                + bytes([0x80 if frame.keyframe else 0])
                + payload
            )
            output.write(
                _element(
                    0x1F43B675,
                    _uint(0xE7, frame.timestamp_ms - origin)
                    + _element(0xA3, block),
                )
            )


def render_archive_mp4(
    media: ArchiveMedia,
    *,
    directory: Path,
    executable: str,
    deadline: float,
    max_bytes: int,
) -> bytes:
    """Remux validated video; clean private intermediates on every outcome."""
    remaining(deadline)
    try:
        directory.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(
            prefix=".quii-archive-", dir=directory
        ) as temporary:
            root = Path(temporary)
            source, target = root / "video.mkv", root / "video.mp4"
            _write_timed_video(source, media, deadline)
            audio_path: Path | None = None
            if media.audio.data:
                audio_path = root / "audio.g711"
                audio_path.write_bytes(media.audio.data)
            command = h264_mp4_command(
                source,
                target,
                input_format="matroska",
                audio_path=audio_path,
                audio_format="alaw" if media.audio.codec == 4 else "mulaw",
                audio_offset_seconds=media.audio.offset_seconds,
                duration_seconds=media.duration_seconds,
            )
            command[0] = executable
            # Do not use -fs: FFmpeg can report success after truncating a clip.
            with (root / "ffmpeg-errors.txt").open("wb") as errors:
                subprocess.run(
                    command,
                    check=True,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=errors,
                    timeout=remaining(deadline),
                )
            remaining(deadline)
            size = target.stat().st_size
            if size > max_bytes:
                raise CameraCaptureError("archive MP4 exceeds max_bytes")
            if size < 12:
                raise MediaRenderError(
                    "FFmpeg did not produce a complete archive MP4"
                )
            result = target.read_bytes()
            remaining(deadline)
            if result[4:8] != b"ftyp":
                raise MediaRenderError(
                    "FFmpeg produced an invalid archive MP4 header"
                )
            return result
    except subprocess.TimeoutExpired as exc:
        raise CameraCaptureError(
            "archive MP4 export exceeded the download deadline"
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise MediaRenderError(
            "FFmpeg could not remux archive video; no partial MP4 returned"
        ) from exc
    except OSError as exc:
        raise MediaRenderError(
            "unable to create or read the temporary archive MP4"
        ) from exc
