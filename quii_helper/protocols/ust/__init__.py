"""UST message and credential crypto helpers."""

from quii_helper.support.lazy import lazy_exports

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

__all__, __getattr__ = lazy_exports(__name__, _EXPORTS, globals())
