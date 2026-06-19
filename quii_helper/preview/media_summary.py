from quii_helper.media.annexb_probe_analysis import analyze_annexb_h264


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
    keyframes = 0
    frame_count = 0
    nal_samples: list[dict] = []
    for decoded in media_messages:
        for frame in _decoded_media_frames(decoded):
            frame_count += 1
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
        "media_frame_count": frame_count,
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


def _frame_nal_analysis(frame: dict) -> dict:
    bitstream = frame.get("bitstream", b"")
    nal_offset = int(frame.get("nal_offset", -1))
    if not isinstance(bitstream, bytes) or nal_offset < 0:
        return {}
    return analyze_annexb_h264(bitstream[nal_offset:])
