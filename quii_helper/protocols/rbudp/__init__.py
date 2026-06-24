"""RB-UDP/KCP tunnel protocol helpers."""

from quii_helper.support.lazy import lazy_exports

_EXPORTS = {
    "DirectKcpQuiiTunnel": (
        "quii_helper.protocols.rbudp.tunnel.session",
        "DirectKcpQuiiTunnel",
    ),
    "ParsedKcpConnectResponse": (
        "quii_helper.protocols.rbudp.core.models",
        "ParsedKcpConnectResponse",
    ),
    "ParsedPacketDispatch": (
        "quii_helper.protocols.rbudp.core.models",
        "ParsedPacketDispatch",
    ),
    "ParsedPacketFrame": (
        "quii_helper.protocols.rbudp.core.models",
        "ParsedPacketFrame",
    ),
    "ParsedRbDataPacket": (
        "quii_helper.protocols.rbudp.core.models",
        "ParsedRbDataPacket",
    ),
    "ParsedRbUdpControlPacket": (
        "quii_helper.protocols.rbudp.core.models",
        "ParsedRbUdpControlPacket",
    ),
    "ParsedRbUdpWrappedPacket": (
        "quii_helper.protocols.rbudp.core.models",
        "ParsedRbUdpWrappedPacket",
    ),
    "RbUdpQuiiTunnel": (
        "quii_helper.protocols.rbudp.tunnel.session",
        "RbUdpQuiiTunnel",
    ),
    "build_kcp_connect_packet": (
        "quii_helper.protocols.rbudp.kcp.link_packets",
        "build_kcp_connect_packet",
    ),
    "build_rb_data_packet": (
        "quii_helper.protocols.rbudp.kcp.link_packets",
        "build_rb_data_packet",
    ),
    "build_rb_udp_control_packet": (
        "quii_helper.protocols.rbudp.control.packets",
        "build_rb_udp_control_packet",
    ),
    "build_rb_udp_wrapped_packet": (
        "quii_helper.protocols.rbudp.wrapped.packets",
        "build_rb_udp_wrapped_packet",
    ),
    "parse_rb_udp_control_packet": (
        "quii_helper.protocols.rbudp.control.packets",
        "parse_rb_udp_control_packet",
    ),
    "parse_rb_udp_wrapped_packet": (
        "quii_helper.protocols.rbudp.wrapped.packets",
        "parse_rb_udp_wrapped_packet",
    ),
}

__all__, __getattr__ = lazy_exports(__name__, _EXPORTS, globals())
