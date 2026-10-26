from dataclasses import dataclass
from typing import Any

from quii_helper.media.audio.recording import AudioRecording
from quii_helper.media.frames.assembler_state import (
    MEDIA_PACKET_TYPES,
    access_unit_from_frame,
    assemble_access_units,
    build_media_summary,
    frame_info_from_parsed_frame,
)
from quii_helper.media.frames.parsing import QuiiCFramePack
from quii_helper.models.capture import MediaFrameSummary


@dataclass
class AssembledH264Stream:
    stream_bytes: bytes
    frames: list[MediaFrameSummary]
    summary: dict[str, Any]
    audio: AudioRecording | None = None

    @property
    def has_access_units(self) -> bool:
        return bool(self.stream_bytes)


def assemble_h264_stream_from_messages(
    messages: list[dict[str, Any]],
    *,
    collect_audio: bool = False,
) -> AssembledH264Stream:
    parsed_frames, frame_info, cframe_stats = _parse_video_frames(messages)
    access_units = assemble_access_units(parsed_frames)
    audio = AudioRecording() if collect_audio else None
    if audio is not None:
        for frame in parsed_frames:
            if access_unit_from_frame(frame):
                audio.start_video(frame)
            elif frame["frame_tag"] == 0xE3:
                audio.feed(frame)
    return AssembledH264Stream(
        stream_bytes=b"".join(access_units),
        frames=frame_info,
        summary=build_media_summary(
            frame_info,
            assembled_units=len(access_units),
            cframe_stats=cframe_stats,
        ),
        audio=audio,
    )


def _parse_video_frames(
    messages: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[MediaFrameSummary], dict[str, int]]:
    packer = QuiiCFramePack()
    parsed_frames: list[dict[str, Any]] = []
    frame_info: list[MediaFrameSummary] = []
    for msg in messages:
        header = msg.get("header")
        if header is None or header.packet_type not in MEDIA_PACKET_TYPES:
            continue
        payload = msg.get("payload", b"")
        if not isinstance(payload, bytes):
            continue
        for frame in packer.feed(payload):
            parsed_frames.append(frame)
            frame_info.append(frame_info_from_parsed_frame(frame))
    return parsed_frames, frame_info, dict(packer.stats)
