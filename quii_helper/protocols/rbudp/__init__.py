"""RB-UDP/KCP tunnel protocol helpers."""

from importlib import import_module
from typing import Any

_EXPORTS = {
    "DirectKcpQuiiTunnel": (
        "quii_helper.protocols.rbudp.tunnel",
        "DirectKcpQuiiTunnel",
    ),
    "ParsedKcpConnectResponse": (
        "quii_helper.protocols.rbudp.models",
        "ParsedKcpConnectResponse",
    ),
    "ParsedPacketDispatch": (
        "quii_helper.protocols.rbudp.models",
        "ParsedPacketDispatch",
    ),
    "ParsedPacketFrame": (
        "quii_helper.protocols.rbudp.models",
        "ParsedPacketFrame",
    ),
    "ParsedRbDataPacket": (
        "quii_helper.protocols.rbudp.models",
        "ParsedRbDataPacket",
    ),
    "ParsedRbUdpControlPacket": (
        "quii_helper.protocols.rbudp.models",
        "ParsedRbUdpControlPacket",
    ),
    "ParsedRbUdpWrappedPacket": (
        "quii_helper.protocols.rbudp.models",
        "ParsedRbUdpWrappedPacket",
    ),
    "RbUdpQuiiTunnel": (
        "quii_helper.protocols.rbudp.tunnel",
        "RbUdpQuiiTunnel",
    ),
    "build_kcp_connect_packet": (
        "quii_helper.protocols.rbudp.kcp_link_packets",
        "build_kcp_connect_packet",
    ),
    "build_rb_data_packet": (
        "quii_helper.protocols.rbudp.kcp_link_packets",
        "build_rb_data_packet",
    ),
    "build_rb_udp_control_packet": (
        "quii_helper.protocols.rbudp.control_packets",
        "build_rb_udp_control_packet",
    ),
    "build_rb_udp_wrapped_packet": (
        "quii_helper.protocols.rbudp.wrapped_packets",
        "build_rb_udp_wrapped_packet",
    ),
    "parse_rb_udp_control_packet": (
        "quii_helper.protocols.rbudp.control_packets",
        "parse_rb_udp_control_packet",
    ),
    "parse_rb_udp_wrapped_packet": (
        "quii_helper.protocols.rbudp.wrapped_packets",
        "parse_rb_udp_wrapped_packet",
    ),
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    try:
        module_name, attr_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(
            f"module {__name__!r} has no attribute {name!r}"
        ) from exc
    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value
