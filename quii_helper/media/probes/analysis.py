"""Backward-compatible probe analysis facade."""

from quii_helper.media.cpacket.analysis import (
    CPACKET_HEADER_LEN,
    CPACKET_START_PREFIX,
    CPACKET_START_TYPE_MAX,
    CPACKET_START_TYPE_MIN,
    analyze_cpacket_stream,
    cpacket_codec_name,
    find_cpacket_offsets,
    parse_cpacket_header,
)
from quii_helper.media.h264.merge.probe_analysis import (
    analyze_annexb_h264,
    find_annexb_start_codes,
)
from quii_helper.media.merge.binary import merge_binary_candidates
from quii_helper.media.probes.container import analyze_container_probe

__all__ = [
    "CPACKET_HEADER_LEN",
    "CPACKET_START_PREFIX",
    "CPACKET_START_TYPE_MAX",
    "CPACKET_START_TYPE_MIN",
    "analyze_annexb_h264",
    "analyze_container_probe",
    "analyze_cpacket_stream",
    "cpacket_codec_name",
    "find_annexb_start_codes",
    "find_cpacket_offsets",
    "merge_binary_candidates",
    "parse_cpacket_header",
]
