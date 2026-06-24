"""Backward-compatible P2P protocol facade.

New code should import from:
- `quii_helper.protocols.p2p.models`
- `quii_helper.protocols.p2p.messages.session`
- `quii_helper.protocols.p2p.codec.json_codec`
- `quii_helper.protocols.p2p.transport.udp`
"""

from quii_helper.protocols.p2p.codec.json_codec import (
    maybe_int,
    parse_p2pconnect_response,
    parse_sub_device_state_response,
)
from quii_helper.protocols.p2p.messages.session import (
    create_request_session_id,
    create_session_flag,
)
from quii_helper.protocols.p2p.models import (
    KcpParams,
    P2PConnectRequest,
    P2PConnectResponse,
    P2PTestTarget,
    ParsedKcpParams,
    ParsedP2PTestResponse,
    ParsedP2PTransportFrame,
    ParsedSubDeviceState,
)
from quii_helper.protocols.p2p.transport.udp import (
    build_p2p_active_packet,
    build_p2p_test_packet,
    build_p2p_transport_ack,
    build_p2p_transport_packet,
    iter_p2p_test_targets,
    parse_p2p_test_response,
    parse_p2p_transport_frame,
)

_maybe_int = maybe_int

__all__ = [
    "KcpParams",
    "P2PConnectRequest",
    "P2PConnectResponse",
    "P2PTestTarget",
    "ParsedKcpParams",
    "ParsedP2PTestResponse",
    "ParsedP2PTransportFrame",
    "ParsedSubDeviceState",
    "build_p2p_active_packet",
    "build_p2p_test_packet",
    "build_p2p_transport_ack",
    "build_p2p_transport_packet",
    "create_request_session_id",
    "create_session_flag",
    "iter_p2p_test_targets",
    "maybe_int",
    "_maybe_int",
    "parse_p2p_test_response",
    "parse_p2p_transport_frame",
    "parse_p2pconnect_response",
    "parse_sub_device_state_response",
]
