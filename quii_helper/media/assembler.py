from dataclasses import dataclass


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
    parsed_frames, frame_info = _parse_video_frames(messages)
    access_units = _assemble_access_units(parsed_frames)
    return AssembledH264Stream(
        stream_bytes=b"".join(access_units),
        frames=frame_info,
        summary=_build_media_summary(
            frame_info, assembled_units=len(access_units)
        ),
    )


def _parse_video_frames(messages: list[dict]) -> tuple[list[dict], list[dict]]:
    parsed_frames = []
    frame_info = []
    for msg in messages:
        header = msg.get("header")
        if header is None or header.packet_type != 0xA0:
            continue
        for frame in _message_media_frames(msg):
            parsed_frames.append(frame)
            frame_info.append(
                {
                    "payload_offset": frame["payload_offset"],
                    "frame_tag": hex(frame["frame_tag"]),
                    "frame_len": frame["frame_len"],
                    "frame_stamp": frame["frame_stamp"],
                    "width": frame["width"],
                    "height": frame["height"],
                    "nal_offset": frame["nal_offset"],
                }
            )
    return parsed_frames, frame_info


def _message_media_frames(msg: dict) -> list[dict]:
    frames = msg.get("media_frames")
    if isinstance(frames, list):
        return [frame for frame in frames if isinstance(frame, dict)]

    frame = msg.get("media_frame")
    if isinstance(frame, dict):
        return [frame]

    return []


def _assemble_access_units(parsed_frames: list[dict]) -> list[bytes]:
    access_units: list[bytes] = []
    for frame in parsed_frames:
        if frame["frame_tag"] not in (0xE0, 0xE1) or frame["nal_offset"] < 0:
            continue
        access_unit = frame["bitstream"][frame["nal_offset"] :]
        if access_unit:
            access_units.append(access_unit)
    return access_units


def _build_media_summary(
    frame_info: list[dict], *, assembled_units: int
) -> dict:
    video_frames = [
        frame for frame in frame_info if frame["frame_tag"] in ("0xe0", "0xe1")
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
        1 for frame in frame_info if frame["frame_tag"] == "0xe1"
    )
    return {
        "video_frames": len(video_frames),
        "keyframes": keyframe_count,
        "e3_frames": len(e3_frames),
        "assembled_units": assembled_units,
        "avg_video_frame_len": avg_video_frame_len,
        "max_video_frame_len": max_video_frame_len,
        "suspect_black_stream": bool(video_frames)
        and max_video_frame_len < 1200,
    }
