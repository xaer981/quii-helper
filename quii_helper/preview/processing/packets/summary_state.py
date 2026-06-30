from collections.abc import Mapping
from typing import Any, cast

from quii_helper.models.packets import QuiiPacketSummary


def media_frame_summary_fields(
    decoded: Mapping[str, Any],
) -> QuiiPacketSummary | None:
    frames = decoded.get("media_frames")
    if not isinstance(frames, list):
        frame = decoded.get("media_frame")
        frames = [frame] if isinstance(frame, dict) else []
    frames = [frame for frame in frames if isinstance(frame, dict)]
    if not frames:
        return None

    frame = frames[0]
    fields = {
        "media_frame_count": len(frames),
        "frame_tag": hex(frame["frame_tag"]),
        "frame_len": frame["frame_len"],
        "frame_stamp": frame["frame_stamp"],
        "width": frame["width"],
        "height": frame["height"],
    }
    if len(frames) > 1:
        fields["frame_tags"] = [
            hex(int(item["frame_tag"])) for item in frames[:8]
        ]
    return cast(QuiiPacketSummary, fields)
