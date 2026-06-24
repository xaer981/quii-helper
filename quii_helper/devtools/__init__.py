"""Development and protocol probing helpers.

These helpers are useful while reverse-engineering or validating protocol
behavior, but they are not part of the normal `Camera` capture path.
"""

from quii_helper.support.lazy import lazy_exports

_EXPORTS = {
    "CameraPreviewApplication": (
        "quii_helper.devtools.preview_application",
        "CameraPreviewApplication",
    ),
    "TcpProbeRunner": ("quii_helper.devtools.tcp_runner", "TcpProbeRunner"),
    "configure_console_output": (
        "quii_helper.devtools.console",
        "configure_console_output",
    ),
    "emit_json_line": ("quii_helper.devtools.console", "emit_json_line"),
    "probe_mode": ("quii_helper.devtools.tcp_runner", "probe_mode"),
    "run_cloud_flow": ("quii_helper.devtools.tcp_runner", "run_cloud_flow"),
    "run_quii_probe": ("quii_helper.devtools.tcp_runner", "run_quii_probe"),
    "try_mode": ("quii_helper.devtools.tcp_runner", "try_mode"),
}

__all__, __getattr__ = lazy_exports(__name__, _EXPORTS, globals())
