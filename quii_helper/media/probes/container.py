from quii_helper.media.cpacket.stream import analyze_cpacket_stream
from quii_helper.media.h264.merge.probe_analysis import analyze_annexb_h264


def analyze_container_probe(blob: bytes) -> dict:
    marker = bytes.fromhex("c0034002")
    marker_hits: list[int] = []
    cursor = 0
    while len(marker_hits) < 16:
        idx = blob.find(marker, cursor)
        if idx < 0:
            break
        marker_hits.append(idx)
        cursor = idx + len(marker)

    header0 = blob[:4]
    header1 = blob[4:8]
    nested = blob[4:] if len(blob) >= 4 else b""
    nested_start_code = nested.find(b"\x00\x00\x00\x01") if nested else -1
    nested_annexb = (
        analyze_annexb_h264(nested)
        if nested.startswith(b"\x00\x00\x00\x01")
        else {}
    )
    false_nested_annexb = bool(nested_annexb.get("false_positive_sps_only"))
    cpacket_analysis = analyze_cpacket_stream(blob)
    return {
        "blob_len": len(blob),
        "classification": (
            "false_nested_annexb_probe"
            if false_nested_annexb
            else "unknown_container_probe"
        ),
        "prefix_hex": blob[:64].hex(),
        "suffix_hex": blob[-64:].hex() if blob else "",
        "header0_hex": header0.hex(),
        "header1_hex": header1.hex(),
        "header0_le": (
            int.from_bytes(header0, "little") if len(header0) == 4 else None
        ),
        "header0_be": (
            int.from_bytes(header0, "big") if len(header0) == 4 else None
        ),
        "header1_le": (
            int.from_bytes(header1, "little") if len(header1) == 4 else None
        ),
        "header1_be": (
            int.from_bytes(header1, "big") if len(header1) == 4 else None
        ),
        "marker_hits": marker_hits,
        "starts_with_probe_magic": header0 == marker,
        "nested_len": len(nested),
        "nested_start_code_at": nested_start_code,
        "nested_prefix_hex": nested[:64].hex(),
        "nested_annexb": nested_annexb,
        "false_nested_annexb": false_nested_annexb,
        "cpacket_analysis": cpacket_analysis,
    }
