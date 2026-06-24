"""Local device CGI and stream-key helpers."""

from quii_helper.support.lazy import lazy_exports

_EXPORTS = {
    "DeviceCgiProbeRunner": (
        "quii_helper.device.probes.flow",
        "DeviceCgiProbeRunner",
    ),
    "build_request_xml": ("quii_helper.device.http.xml", "build_request_xml"),
    "encode_device_password": (
        "quii_helper.device.security.auth",
        "encode_device_password",
    ),
    "get_encrypt_password": (
        "quii_helper.device.security.auth",
        "get_encrypt_password",
    ),
    "probe_mode": ("quii_helper.device.probes.flow", "probe_mode"),
    "request_cgi": ("quii_helper.device.http.transport", "request_cgi"),
    "request_streamkey": (
        "quii_helper.device.security.streamkey",
        "request_streamkey",
    ),
    "try_mode": ("quii_helper.device.probes.flow", "try_mode"),
}

__all__, __getattr__ = lazy_exports(__name__, _EXPORTS, globals())
