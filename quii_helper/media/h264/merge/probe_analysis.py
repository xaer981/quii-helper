from typing import Any

from quii_helper.media.h264.core.annexb import (
    analyze_nal_units,
    emulation_prevention_byte_count,
    find_start_codes,
)


def find_annexb_start_codes(buf: bytes) -> list[tuple[int, int]]:
    return find_start_codes(buf)


def analyze_annexb_h264(stream: bytes) -> dict[str, Any]:
    summary = analyze_nal_units(stream)
    counts = summary["counts"]
    epb_count = emulation_prevention_byte_count(stream)
    has_vcl = bool(summary["has_vcl"])
    has_pps = bool(summary["has_pps"])
    has_sei = bool(counts.get("sei"))
    has_sps = bool(summary["has_sps"])
    false_positive_sps_only = (
        has_sps
        and not has_pps
        and not has_sei
        and not has_vcl
        and set(counts.keys()) <= {"sps"}
        and summary["start_code_count"] <= 2
        and epb_count == 0
        and summary["largest_payload_len"] >= 512
    )

    return {
        **summary,
        "has_sei": has_sei,
        "epb_count": epb_count,
        "false_positive_sps_only": false_positive_sps_only,
    }
