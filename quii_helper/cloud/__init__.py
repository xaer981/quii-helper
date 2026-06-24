"""Cloud authentication and service discovery helpers."""

from quii_helper.support.lazy import lazy_exports

_EXPORTS = {
    "CloudProbeFlow": ("quii_helper.cloud.flows.probe_flow", "CloudProbeFlow"),
    "fetch_runtime_credentials": (
        "quii_helper.cloud.services.discovery",
        "fetch_runtime_credentials",
    ),
    "get_device_token": (
        "quii_helper.cloud.authentication.auth",
        "get_device_token",
    ),
    "login_cloud": ("quii_helper.cloud.authentication.auth", "login_cloud"),
    "populate_discovered_services": (
        "quii_helper.cloud.services.discovery",
        "populate_discovered_services",
    ),
    "query_service_addresses": (
        "quii_helper.cloud.services.discovery",
        "query_service_addresses",
    ),
    "run_cloud_flow": ("quii_helper.cloud.flows.probe_flow", "run_cloud_flow"),
}

__all__, __getattr__ = lazy_exports(__name__, _EXPORTS, globals())
