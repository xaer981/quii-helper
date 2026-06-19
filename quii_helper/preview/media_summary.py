from quii_helper.media.annexb_probe_analysis import analyze_annexb_h264
from quii_helper.media.parsing import QuiiCFramePack

MEDIA_PACKET_TYPES = {0xA0, 0xA1, 0xA2, 0xA3}


def media_message_nal_analysis(decoded: dict) -> dict:
    frames = _decoded_media_frames(decoded)
    frame = frames[0] if frames else None
    if not isinstance(frame, dict):
        return {}
    bitstream = frame.get("bitstream", b"")
    nal_offset = int(frame.get("nal_offset", -1))
    if not isinstance(bitstream, bytes) or nal_offset < 0:
        return {}
    return analyze_annexb_h264(bitstream[nal_offset:])


def media_collection_summary(media_messages: list[dict]) -> dict:
    counts: dict[str, int] = {}
    has_sps = False
    has_pps = False
    has_idr = False
    has_vcl = False
    media_decrypt_packets = 0
    media_decrypt_bytes = 0
    media_decrypt_candidate_packets = 0
    media_decrypt_candidate_bytes = 0
    nal_samples: list[dict] = []
    frames, cframe_stats = _stateful_media_frames(media_messages)
    for decoded in media_messages:
        candidate_len = int(decoded.get("media_decrypt_candidate_len", 0))
        if candidate_len > 0:
            media_decrypt_candidate_packets += 1
            media_decrypt_candidate_bytes += candidate_len
        if decoded.get("media_decrypt_applied"):
            media_decrypt_packets += 1
            media_decrypt_bytes += int(decoded.get("media_decrypt_len", 0))

    keyframes = 0
    for frame in frames:
        if int(frame.get("frame_tag", -1)) == 0xE1:
            keyframes += 1
        nal = _frame_nal_analysis(frame)
        for name, count in dict(nal.get("counts", {})).items():
            counts[name] = counts.get(name, 0) + int(count)
        has_sps = has_sps or bool(nal.get("has_sps"))
        has_pps = has_pps or bool(nal.get("has_pps"))
        has_idr = has_idr or bool(nal.get("has_idr"))
        has_vcl = has_vcl or bool(nal.get("has_vcl"))
        if nal and len(nal_samples) < 6:
            nal_samples.append(
                {
                    "frame_tag": hex(int(frame.get("frame_tag", 0))),
                    "frame_len": int(frame.get("frame_len", 0)),
                    "cframe_fragments": int(frame.get("cframe_fragments", 0)),
                    "nal": {
                        "counts": nal.get("counts", {}),
                        "has_sps": nal.get("has_sps"),
                        "has_pps": nal.get("has_pps"),
                        "has_idr": nal.get("has_idr"),
                        "nal_units": nal.get("nal_units", [])[:3],
                    },
                }
            )
    return {
        "media_messages": len(media_messages),
        "media_frame_count": len(frames),
        "cframe_pack": cframe_stats,
        "media_decrypt_candidate_packets": (media_decrypt_candidate_packets),
        "media_decrypt_candidate_bytes": media_decrypt_candidate_bytes,
        "media_decrypt_packets": media_decrypt_packets,
        "media_decrypt_bytes": media_decrypt_bytes,
        "keyframes": keyframes,
        "has_sps": has_sps,
        "has_pps": has_pps,
        "has_idr": has_idr,
        "has_vcl": has_vcl,
        "counts": counts,
        "nal_samples": nal_samples,
        "decodable_h264_context": bool(has_sps and has_pps and has_vcl),
    }


def _decoded_media_frames(decoded: dict) -> list[dict]:
    frames = decoded.get("media_frames")
    if isinstance(frames, list):
        return [frame for frame in frames if isinstance(frame, dict)]
    frame = decoded.get("media_frame")
    return [frame] if isinstance(frame, dict) else []


def _stateful_media_frames(
    media_messages: list[dict],
) -> tuple[list[dict], dict]:
    packer = QuiiCFramePack()
    frames: list[dict] = []
    for decoded in media_messages:
        header = decoded.get("header")
        if header is None or header.packet_type not in MEDIA_PACKET_TYPES:
            continue
        payload = decoded.get("payload", b"")
        if isinstance(payload, bytes):
            frames.extend(packer.feed(payload))
    return frames, dict(packer.stats)


def _frame_nal_analysis(frame: dict) -> dict:
    bitstream = frame.get("bitstream", b"")
    nal_offset = int(frame.get("nal_offset", -1))
    if not isinstance(bitstream, bytes) or nal_offset < 0:
        return {}
    return analyze_annexb_h264(bitstream[nal_offset:])
