"""Local device CGI and stream-key helpers."""

from importlib import import_module
from typing import Any

_EXPORTS = {
    "DeviceCgiProbeRunner": (
        "quii_helper.device.probe_flow",
        "DeviceCgiProbeRunner",
    ),
    "build_request_xml": ("quii_helper.device.xml", "build_request_xml"),
    "encode_device_password": (
        "quii_helper.device.auth",
        "encode_device_password",
    ),
    "get_encrypt_password": (
        "quii_helper.device.auth",
        "get_encrypt_password",
    ),
    "probe_mode": ("quii_helper.device.probe_flow", "probe_mode"),
    "request_cgi": ("quii_helper.device.transport", "request_cgi"),
    "request_streamkey": ("quii_helper.device.streamkey", "request_streamkey"),
    "try_mode": ("quii_helper.device.probe_flow", "try_mode"),
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
