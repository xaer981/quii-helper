"""Backward-compatible QUII live protocol facade."""

from quii_helper.protocols.quii.live_packets import (
    build_live_fastplay_packet,
    build_live_keepalive_packet,
    build_live_play_oem_packet,
    build_live_play_packet,
    build_live_play_packet_from_body,
    build_live_setup_packet,
)
from quii_helper.protocols.quii.live_rb import (
    build_direct_quii_play_oem_rb,
    build_direct_quii_play_rb,
    build_direct_quii_setup_rb,
)

_build_live_play_packet_from_body = build_live_play_packet_from_body

__all__ = [
    "_build_live_play_packet_from_body",
    "build_direct_quii_play_oem_rb",
    "build_direct_quii_play_rb",
    "build_direct_quii_setup_rb",
    "build_live_fastplay_packet",
    "build_live_keepalive_packet",
    "build_live_play_oem_packet",
    "build_live_play_packet",
    "build_live_play_packet_from_body",
    "build_live_setup_packet",
]
