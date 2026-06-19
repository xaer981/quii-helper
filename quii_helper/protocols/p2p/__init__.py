"""P2P connect, probing, and transport helpers."""

from importlib import import_module
from typing import Any

_EXPORTS = {
    "KcpParams": ("quii_helper.protocols.p2p.models", "KcpParams"),
    "P2PConnectRequest": (
        "quii_helper.protocols.p2p.models",
        "P2PConnectRequest",
    ),
    "P2PConnectResponse": (
        "quii_helper.protocols.p2p.models",
        "P2PConnectResponse",
    ),
    "P2PTestTarget": ("quii_helper.protocols.p2p.models", "P2PTestTarget"),
    "ParsedKcpParams": ("quii_helper.protocols.p2p.models", "ParsedKcpParams"),
    "ParsedP2PTestResponse": (
        "quii_helper.protocols.p2p.models",
        "ParsedP2PTestResponse",
    ),
    "ParsedP2PTransportFrame": (
        "quii_helper.protocols.p2p.models",
        "ParsedP2PTransportFrame",
    ),
    "ParsedSubDeviceState": (
        "quii_helper.protocols.p2p.models",
        "ParsedSubDeviceState",
    ),
    "create_request_session_id": (
        "quii_helper.protocols.p2p.session",
        "create_request_session_id",
    ),
    "create_session_flag": (
        "quii_helper.protocols.p2p.session",
        "create_session_flag",
    ),
    "parse_p2pconnect_response": (
        "quii_helper.protocols.p2p.json_codec",
        "parse_p2pconnect_response",
    ),
    "parse_sub_device_state_response": (
        "quii_helper.protocols.p2p.json_codec",
        "parse_sub_device_state_response",
    ),
    "run_p2p_active_handshake": (
        "quii_helper.protocols.p2p.active_handshake",
        "run_p2p_active_handshake",
    ),
    "run_udp_probe": ("quii_helper.protocols.p2p.udp_probe", "run_udp_probe"),
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
