from dataclasses import dataclass

from quii_helper.media.frames.assembler_state import (
    MEDIA_PACKET_TYPES,
    assemble_access_units,
    build_media_summary,
    frame_info_from_parsed_frame,
)
from quii_helper.media.frames.parsing import QuiiCFramePack


@dataclass
class AssembledH264Stream:
    stream_bytes: bytes
    frames: list[dict]
    summary: dict

    @property
    def has_access_units(self) -> bool:
        return bool(self.stream_bytes)


def assemble_h264_stream_from_messages(
    messages: list[dict],
) -> AssembledH264Stream:
    parsed_frames, frame_info, cframe_stats = _parse_video_frames(messages)
    access_units = assemble_access_units(parsed_frames)
    return AssembledH264Stream(
        stream_bytes=b"".join(access_units),
        frames=frame_info,
        summary=build_media_summary(
            frame_info,
            assembled_units=len(access_units),
            cframe_stats=cframe_stats,
        ),
    )


def _parse_video_frames(
    messages: list[dict],
) -> tuple[list[dict], list[dict], dict[str, int]]:
    packer = QuiiCFramePack()
    parsed_frames = []
    frame_info = []
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
