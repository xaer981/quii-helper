"""Backward-compatible P2P UDP facade."""

from quii_helper.protocols.p2p.peers.targets import iter_p2p_test_targets
from quii_helper.protocols.p2p.probing.test_packets import (
    build_p2p_test_packet,
    parse_p2p_test_response,
)
from quii_helper.protocols.p2p.transport.packets import (
    build_p2p_active_packet,
    build_p2p_transport_ack,
    build_p2p_transport_packet,
    parse_p2p_transport_frame,
)

__all__ = [
    "build_p2p_active_packet",
    "build_p2p_test_packet",
    "build_p2p_transport_ack",
    "build_p2p_transport_packet",
    "iter_p2p_test_targets",
    "parse_p2p_test_response",
    "parse_p2p_transport_frame",
]
