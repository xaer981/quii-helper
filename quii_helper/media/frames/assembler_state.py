MEDIA_PACKET_TYPES = {0xA0, 0xA1, 0xA2, 0xA3}
VIDEO_FRAME_TAGS = {0xE0, 0xE1, 0xE9, 0xEA}
KEY_FRAME_TAGS = {0xE1}
VIDEO_FRAME_TYPES = {0, 1, 9, 10}


def frame_info_from_parsed_frame(frame: dict) -> dict:
    return {
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


def access_unit_from_frame(frame: dict) -> bytes:
    if frame["frame_tag"] not in VIDEO_FRAME_TAGS or frame["nal_offset"] < 0:
        return b""
    return frame["bitstream"][frame["nal_offset"] :]


def assemble_access_units(parsed_frames: list[dict]) -> list[bytes]:
    return [
        access_unit
        for frame in parsed_frames
        if (access_unit := access_unit_from_frame(frame))
    ]


def is_video_frame_info(frame: dict) -> bool:
    return int(frame["frame_type"]) in VIDEO_FRAME_TYPES


def is_key_frame_info(frame: dict) -> bool:
    return int(frame["frame_tag"], 16) in KEY_FRAME_TAGS


def media_frame_length_stats(video_frames: list[dict]) -> tuple[int, int]:
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
    return avg_video_frame_len, max_video_frame_len


def build_media_summary(
    frame_info: list[dict],
    *,
    assembled_units: int,
    cframe_stats: dict[str, int],
) -> dict:
    video_frames = [
        frame for frame in frame_info if is_video_frame_info(frame)
    ]
    e3_frames = [frame for frame in frame_info if frame["frame_tag"] == "0xe3"]
    avg_video_frame_len, max_video_frame_len = media_frame_length_stats(
        video_frames
    )
    keyframe_count = sum(1 for frame in frame_info if is_key_frame_info(frame))
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
