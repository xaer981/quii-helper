def find_annexb_start_codes(buf: bytes) -> list[tuple[int, int]]:
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


def analyze_annexb_h264(stream: bytes) -> dict:
    nal_type_names = {
        1: "non_idr_slice",
        5: "idr_slice",
        6: "sei",
        7: "sps",
        8: "pps",
        9: "aud",
    }
    starts = find_annexb_start_codes(stream)
    nal_units: list[dict] = []
    counts: dict[str, int] = {}
    epb_count = sum(
        1
        for i in range(2, len(stream))
        if stream[i] == 0x03
        and stream[i - 1] == 0x00
        and stream[i - 2] == 0x00
    )
    largest_payload_len = 0
    for idx, (start, sc_len) in enumerate(starts):
        payload_start = start + sc_len
        payload_end = (
            starts[idx + 1][0] if idx + 1 < len(starts) else len(stream)
        )
        if payload_start >= payload_end:
            continue
        nal_header = stream[payload_start]
        nal_type = nal_header & 0x1F
        name = nal_type_names.get(nal_type, f"type_{nal_type}")
        counts[name] = counts.get(name, 0) + 1
        payload_len = payload_end - payload_start
        largest_payload_len = max(largest_payload_len, payload_len)
        if len(nal_units) < 16:
            nal_units.append(
                {
                    "offset": start,
                    "start_code_len": sc_len,
                    "nal_type": nal_type,
                    "nal_name": name,
                    "payload_len": payload_len,
                    "header_byte": hex(nal_header),
                }
            )

    has_vcl = bool(counts.get("idr_slice") or counts.get("non_idr_slice"))
    has_pps = bool(counts.get("pps"))
    has_sei = bool(counts.get("sei"))
    has_sps = bool(counts.get("sps"))
    false_positive_sps_only = (
        has_sps
        and not has_pps
        and not has_sei
        and not has_vcl
        and set(counts.keys()) <= {"sps"}
        and len(starts) <= 2
        and epb_count == 0
        and largest_payload_len >= 512
    )

    return {
        "stream_len": len(stream),
        "start_code_count": len(starts),
        "nal_count": sum(counts.values()),
        "counts": counts,
        "has_vcl": has_vcl,
        "has_idr": bool(counts.get("idr_slice")),
        "has_sps": has_sps,
        "has_pps": has_pps,
        "has_sei": has_sei,
        "epb_count": epb_count,
        "largest_payload_len": largest_payload_len,
        "false_positive_sps_only": false_positive_sps_only,
        "nal_units": nal_units,
    }
