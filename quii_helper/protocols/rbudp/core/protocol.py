"""Backward-compatible RB-UDP/KCP protocol facade.

New code should import from:
- `quii_helper.protocols.rbudp.core.models`
- `quii_helper.protocols.rbudp.kcp.link_packets`
- `quii_helper.protocols.rbudp.core.packets`
"""

from quii_helper.protocols.rbudp.control.packets import (
    build_rb_udp_control_packet,
    parse_rb_udp_control_packet,
)
from quii_helper.protocols.rbudp.core.models import (
    ParsedKcpConnectResponse,
    ParsedPacketDispatch,
    ParsedPacketFrame,
    ParsedRbDataPacket,
    ParsedRbUdpControlPacket,
    ParsedRbUdpWrappedPacket,
)
from quii_helper.protocols.rbudp.kcp.link_packets import (
    build_kcp_connect_packet,
    build_kcp_conv,
    build_kcp_disconnect_packet,
    build_rb_data_ack_packet,
    build_rb_data_packet,
    iter_kcp_packet_frames,
    parse_kcp_connect_response,
    parse_kcp_packet_frame,
    parse_rb_data_packet,
)
from quii_helper.protocols.rbudp.wrapped.packets import (
    build_rb_udp_wrapped_packet,
    classify_rb_udp_packet,
    parse_rb_udp_wrapped_packet,
)

__all__ = [
    "ParsedKcpConnectResponse",
    "ParsedPacketDispatch",
    "ParsedPacketFrame",
    "ParsedRbDataPacket",
    "ParsedRbUdpControlPacket",
    "ParsedRbUdpWrappedPacket",
    "build_kcp_connect_packet",
    "build_kcp_conv",
    "build_kcp_disconnect_packet",
    "build_rb_data_ack_packet",
    "build_rb_data_packet",
    "build_rb_udp_control_packet",
    "build_rb_udp_wrapped_packet",
    "classify_rb_udp_packet",
    "iter_kcp_packet_frames",
    "parse_kcp_connect_response",
    "parse_kcp_packet_frame",
    "parse_rb_data_packet",
    "parse_rb_udp_control_packet",
    "parse_rb_udp_wrapped_packet",
]
