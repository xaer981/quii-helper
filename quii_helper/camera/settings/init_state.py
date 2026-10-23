from collections.abc import Mapping
from typing import Any

CAMERA_CONFIG_KWARG_NAMES = (
    "connection_mode",
    "stream_port",
    "stream_key",
    "device_id",
    "cloud_username",
    "cloud_account",
    "cloud_password",
    "device_host",
    "auth_code",
    "unlock_password",
    "client_id",
    "service_url",
    "auth_url",
    "oem",
    "app_id",
    "client_type",
    "ca_path",
    "cert_path",
    "key_path",
    "ip_region_id",
    "live_play_payload",
    "live_inner",
    "live_newcn",
    "live_keepalive_interval",
    "play_sync_iterations",
    "enable_play_probes",
    "tls_verify",
    "channel",
    "stream",
    "stream_quality",
    "assets_dir",
    "auth_version",
)


def camera_config_kwargs(values: Mapping[str, Any]) -> dict[str, Any]:
    return {name: values[name] for name in CAMERA_CONFIG_KWARG_NAMES}
