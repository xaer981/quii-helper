"""QUII crypto, blob, URL, and live packet helpers."""

from importlib import import_module
from typing import Any

_EXPORTS = {
    "aes_cbc_crypt": ("quii_helper.protocols.quii.crypto", "aes_cbc_crypt"),
    "build_live_keepalive_packet": (
        "quii_helper.protocols.quii.live_packets",
        "build_live_keepalive_packet",
    ),
    "build_live_play_packet": (
        "quii_helper.protocols.quii.live_packets",
        "build_live_play_packet",
    ),
    "build_live_setup_packet": (
        "quii_helper.protocols.quii.live_packets",
        "build_live_setup_packet",
    ),
    "build_quii_live_path": (
        "quii_helper.protocols.quii.url",
        "build_quii_live_path",
    ),
    "build_quii_live_url": (
        "quii_helper.protocols.quii.url",
        "build_quii_live_url",
    ),
    "decode_quii_blob": (
        "quii_helper.protocols.quii.blob",
        "decode_quii_blob",
    ),
    "find_quii_decode_candidates": (
        "quii_helper.protocols.quii.blob",
        "find_quii_decode_candidates",
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
