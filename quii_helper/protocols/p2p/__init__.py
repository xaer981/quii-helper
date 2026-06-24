"""P2P connect, probing, and transport helpers."""

from quii_helper.support.lazy import lazy_exports

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
        "quii_helper.protocols.p2p.messages.session",
        "create_request_session_id",
    ),
    "create_session_flag": (
        "quii_helper.protocols.p2p.messages.session",
        "create_session_flag",
    ),
    "parse_p2pconnect_response": (
        "quii_helper.protocols.p2p.codec.json_codec",
        "parse_p2pconnect_response",
    ),
    "parse_sub_device_state_response": (
        "quii_helper.protocols.p2p.codec.json_codec",
        "parse_sub_device_state_response",
    ),
    "run_p2p_active_handshake": (
        "quii_helper.protocols.p2p.handshake.active",
        "run_p2p_active_handshake",
    ),
    "run_udp_probe": (
        "quii_helper.protocols.p2p.probing.udp_probe",
        "run_udp_probe",
    ),
    "request_models": ("quii_helper.protocols.p2p.models.request", None),
    "response_models": ("quii_helper.protocols.p2p.models.response", None),
}

__all__, __getattr__ = lazy_exports(__name__, _EXPORTS, globals())
