"""Direct P2P preview session helpers."""

from importlib import import_module
from typing import Any

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
