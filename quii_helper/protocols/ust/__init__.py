"""UST message and credential crypto helpers."""

from importlib import import_module
from typing import Any

_EXPORTS = {
    "UST_AES_IV": ("quii_helper.protocols.ust.credentials", "UST_AES_IV"),
    "build_ust_register_request": (
        "quii_helper.protocols.ust.messages",
        "build_ust_register_request",
    ),
    "build_ust_sub_device_state_request": (
        "quii_helper.protocols.ust.messages",
        "build_ust_sub_device_state_request",
    ),
    "build_ust_unregister_request": (
        "quii_helper.protocols.ust.messages",
        "build_ust_unregister_request",
    ),
    "build_ust_update_netinfo_request": (
        "quii_helper.protocols.ust.messages",
        "build_ust_update_netinfo_request",
    ),
    "decode_ust_mqtt_credentials": (
        "quii_helper.protocols.ust.credentials",
        "decode_ust_mqtt_credentials",
    ),
    "decrypt_ust_ciphertext": (
        "quii_helper.protocols.ust.credentials",
        "decrypt_ust_ciphertext",
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
