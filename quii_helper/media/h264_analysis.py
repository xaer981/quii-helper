def find_h264_start_codes(buf: bytes) -> list[tuple[int, int]]:
    starts: list[tuple[int, int]] = []
    i = 0
    end = len(buf) - 3
    while i < end:
        if buf[i : i + 4] == b"\x00\x00\x00\x01":
            starts.append((i, 4))
            i += 4
            continue
        if buf[i : i + 3] == b"\x00\x00\x01":
            starts.append((i, 3))
            i += 3
            continue
        i += 1
    return starts


def analyze_h264_annexb_stream(stream: bytes) -> dict:
    nal_names = {
        1: "non_idr_slice",
        5: "idr_slice",
        6: "sei",
        7: "sps",
        8: "pps",
        9: "aud",
    }
    starts = find_h264_start_codes(stream)
    counts: dict[str, int] = {}
    nal_units: list[dict] = []
    for idx, (start, sc_len) in enumerate(starts):
        payload_start = start + sc_len
        payload_end = (
            starts[idx + 1][0] if idx + 1 < len(starts) else len(stream)
        )
        if payload_start >= payload_end:
            continue
        nal_header = stream[payload_start]
        nal_type = nal_header & 0x1F
        name = nal_names.get(nal_type, f"type_{nal_type}")
        counts[name] = counts.get(name, 0) + 1
        if len(nal_units) < 16:
            nal_units.append(
                {
                    "offset": start,
                    "start_code_len": sc_len,
                    "nal_type": nal_type,
                    "nal_name": name,
                    "payload_len": payload_end - payload_start,
                    "header_byte": hex(nal_header),
                }
            )
    has_sps = bool(counts.get("sps"))
    has_pps = bool(counts.get("pps"))
    has_idr = bool(counts.get("idr_slice"))
    has_vcl = bool(counts.get("idr_slice") or counts.get("non_idr_slice"))
    return {
        "stream_len": len(stream),
        "start_code_count": len(starts),
        "nal_count": sum(counts.values()),
        "counts": counts,
        "has_sps": has_sps,
        "has_pps": has_pps,
        "has_idr": has_idr,
        "has_vcl": has_vcl,
        "decodable_h264_context": bool(has_sps and has_pps and has_vcl),
        "nal_units": nal_units,
    }
