from quii_helper.media.h264.core.annexb import (
    analyze_nal_units,
    find_start_codes,
)


def find_h264_start_codes(buf: bytes) -> list[tuple[int, int]]:
    return find_start_codes(buf)


def analyze_h264_annexb_stream(stream: bytes) -> dict:
    summary = analyze_nal_units(stream)
    summary.pop("largest_payload_len", None)
    summary["decodable_h264_context"] = bool(
        summary["has_sps"] and summary["has_pps"] and summary["has_vcl"]
    )
    return summary
