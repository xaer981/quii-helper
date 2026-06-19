"""Cloud authentication and service discovery helpers."""

from importlib import import_module
from typing import Any

_EXPORTS = {
    "CloudProbeFlow": ("quii_helper.cloud.probe_flow", "CloudProbeFlow"),
    "fetch_runtime_credentials": (
        "quii_helper.cloud.service_discovery",
        "fetch_runtime_credentials",
    ),
    "get_device_token": ("quii_helper.cloud.auth", "get_device_token"),
    "login_cloud": ("quii_helper.cloud.auth", "login_cloud"),
    "populate_discovered_services": (
        "quii_helper.cloud.service_discovery",
        "populate_discovered_services",
    ),
    "query_service_addresses": (
        "quii_helper.cloud.service_discovery",
        "query_service_addresses",
    ),
    "run_cloud_flow": ("quii_helper.cloud.probe_flow", "run_cloud_flow"),
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
