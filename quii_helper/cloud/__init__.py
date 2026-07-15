"""Cloud authentication and service discovery helpers."""

from quii_helper.cloud.authentication.auth import get_device_token, login_cloud
from quii_helper.cloud.flows.probe_flow import CloudProbeFlow, run_cloud_flow
from quii_helper.cloud.iot import (
    CameraIotCommandSupportInfo,
    fetch_iot_command_support,
)
from quii_helper.cloud.oauth import (
    CloudOAuthToken,
    fetch_oauth_access_token,
)
from quii_helper.cloud.services.discovery import (
    fetch_runtime_credentials,
    populate_discovered_services,
    query_service_addresses,
)
from quii_helper.cloud.shadow import (
    CameraDeviceShadowInfo,
    CameraDeviceShadowState,
    CameraDeviceShadowSwitchState,
    fetch_device_shadow_info,
)

__all__ = [
    "CloudProbeFlow",
    "CameraIotCommandSupportInfo",
    "CameraDeviceShadowInfo",
    "CameraDeviceShadowState",
    "CameraDeviceShadowSwitchState",
    "CloudOAuthToken",
    "fetch_runtime_credentials",
    "fetch_iot_command_support",
    "fetch_oauth_access_token",
    "fetch_device_shadow_info",
    "get_device_token",
    "login_cloud",
    "populate_discovered_services",
    "query_service_addresses",
    "run_cloud_flow",
]
