from dataclasses import dataclass

from quii_helper.media.parsing import QuiiCFramePack

MEDIA_PACKET_TYPES = {0xA0, 0xA1, 0xA2, 0xA3}
VIDEO_FRAME_TAGS = {0xE0, 0xE1, 0xE9, 0xEA}
KEY_FRAME_TAGS = {0xE1}


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
    access_units = _assemble_access_units(parsed_frames)
    return AssembledH264Stream(
        stream_bytes=b"".join(access_units),
        frames=frame_info,
        summary=_build_media_summary(
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
            frame_info.append(
                {
                    "payload_offset": frame["payload_offset"],
                    "frame_tag": hex(frame["frame_tag"]),
                    "frame_type": frame["frame_type"],
                    "frame_len": frame["frame_len"],
                    "frame_stamp": frame["frame_stamp"],
                    "codec": frame["codec"],
                    "fps": frame["fps"],
                    "width": frame["width"],
                    "height": frame["height"],
                    "nal_offset": frame["nal_offset"],
                    "cframe_fragments": frame.get("cframe_fragments", 0),
                }
            )
    return parsed_frames, frame_info, dict(packer.stats)


def _assemble_access_units(parsed_frames: list[dict]) -> list[bytes]:
    access_units: list[bytes] = []
    for frame in parsed_frames:
        if (
            frame["frame_tag"] not in VIDEO_FRAME_TAGS
            or frame["nal_offset"] < 0
        ):
            continue
        access_unit = frame["bitstream"][frame["nal_offset"] :]
        if access_unit:
            access_units.append(access_unit)
    return access_units


def _build_media_summary(
    frame_info: list[dict],
    *,
    assembled_units: int,
    cframe_stats: dict[str, int],
) -> dict:
    video_frames = [
        frame
        for frame in frame_info
        if int(frame["frame_type"]) in (0, 1, 9, 10)
    ]
    e3_frames = [frame for frame in frame_info if frame["frame_tag"] == "0xe3"]
    avg_video_frame_len = (
        int(
            sum(frame["frame_len"] for frame in video_frames)
            / len(video_frames)
        )
        if video_frames
        else 0
    )
    max_video_frame_len = max(
        (frame["frame_len"] for frame in video_frames), default=0
    )
    keyframe_count = sum(
        1
        for frame in frame_info
        if int(frame["frame_tag"], 16) in KEY_FRAME_TAGS
    )
    return {
        "video_frames": len(video_frames),
        "keyframes": keyframe_count,
        "e3_frames": len(e3_frames),
        "assembled_units": assembled_units,
        "cframe_pack": cframe_stats,
        "avg_video_frame_len": avg_video_frame_len,
        "max_video_frame_len": max_video_frame_len,
        "suspect_black_stream": bool(video_frames)
        and max_video_frame_len < 1200,
    }
