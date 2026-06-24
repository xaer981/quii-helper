"""Direct P2P preview session helpers."""

from quii_helper.support.lazy import lazy_exports

_EXPORTS = {
    "establish_direct_p2pconnect_session": (
        "quii_helper.direct.p2p_session",
        "establish_direct_p2pconnect_session",
    ),
    "open_direct_preview": (
        "quii_helper.direct.preview",
        "open_direct_preview",
    ),
    "probe_and_select_direct_peers": (
        "quii_helper.direct.peer_selection",
        "probe_and_select_direct_peers",
    ),
}

__all__, __getattr__ = lazy_exports(__name__, _EXPORTS, globals())
