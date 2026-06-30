from typing import Any

from quii_helper.media.cpacket.header import parse_cpacket_header
from quii_helper.media.cpacket.scanner import find_cpacket_offsets


def analyze_cpacket_stream(blob: bytes) -> dict[str, Any]:
    offsets = find_cpacket_offsets(blob, limit=16)
    frames = [parse_cpacket_header(blob, offset) for offset in offsets[:8]]
    complete_frames = sum(1 for frame in frames if frame.get("complete_frame"))
    plausible_frames = sum(1 for frame in frames if frame.get("plausible"))
    return {
        "blob_len": len(blob),
        "candidate_count": len(offsets),
        "candidate_offsets": offsets,
        "has_cpacket_header": bool(offsets),
        "plausible_frames": plausible_frames,
        "complete_frames": complete_frames,
        "frames": frames,
    }
