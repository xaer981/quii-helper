from quii_helper.support.lazy import lazy_exports

_EXPORTS = {
    "run_p2p_active_handshake": (
        "quii_helper.protocols.p2p.handshake.active",
        "run_p2p_active_handshake",
    ),
    "run_udp_probe": (
        "quii_helper.protocols.p2p.probing.udp_probe",
        "run_udp_probe",
    ),
}

__all__, __getattr__ = lazy_exports(__name__, _EXPORTS, globals())
