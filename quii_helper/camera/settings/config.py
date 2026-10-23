from dataclasses import replace
from pathlib import Path
from typing import Any, cast

from quii_helper.camera.settings.config_state import (
    non_negative_float,
    non_negative_value,
    optional_config_path,
    resolve_cloud_account_alias,
    validate_stream_selector,
)
from quii_helper.config import AutonomousConfig, resolve_stream_quality


def resolve_camera_config(
    config: AutonomousConfig,
    *,
    device_id: str | None,
    cloud_username: str | None,
    cloud_account: str | None,
    cloud_password: str | None,
    device_host: str | None,
    auth_code: str | None,
    client_id: str | None,
    service_url: str | None,
    auth_url: str | None,
    oem: str | None,
    app_id: int | None,
    client_type: int | None,
    ca_path: str | Path | None,
    cert_path: str | Path | None,
    key_path: str | Path | None,
    ip_region_id: int | None,
    live_play_payload: str | None,
    live_inner: bool | None,
    live_newcn: bool | None,
    live_keepalive_interval: float | None,
    play_sync_iterations: int | None,
    enable_play_probes: bool | None,
    tls_verify: bool | None,
    channel: int | None,
    stream: int | None,
    stream_quality: str | int | None,
    unlock_password: str | None = None,
    assets_dir: str | Path | None = None,
    auth_version: str | None = None,
    connection_mode: str | None = None,
    stream_port: int | None = None,
    stream_key: str | None = None,
) -> AutonomousConfig:
    validate_stream_selector(stream=stream, stream_quality=stream_quality)
    resolved_cloud_account = resolve_cloud_account_alias(
        cloud_username=cloud_username,
        cloud_account=cloud_account,
    )
    values: dict[str, object] = {}
    if connection_mode is not None:
        values["connection_mode"] = connection_mode
    if stream_port is not None:
        values["stream_port"] = stream_port
    if stream_key is not None:
        values["stream_key"] = stream_key
    if assets_dir is not None:
        root = Path(assets_dir).expanduser().resolve()
        values.update(
            assets_dir=root,
            ca_path=root / "ca.pem",
            cert_path=root / "client.pem",
            key_path=root / "client.txt",
        )
    if auth_version is not None:
        values["auth_version"] = auth_version
    if device_id is not None:
        values["device_id"] = device_id
    if resolved_cloud_account is not None:
        values["cloud_account"] = resolved_cloud_account
    if cloud_password is not None:
        values["cloud_password"] = cloud_password
    if device_host is not None:
        values["device_host"] = device_host
    if auth_code is not None:
        values["auth_code"] = auth_code
    if unlock_password is not None:
        values["unlock_password"] = unlock_password
    if client_id is not None:
        values["client_id"] = client_id
    if service_url is not None:
        values["service_url"] = service_url
    if auth_url is not None:
        values["auth_url"] = auth_url
    if oem is not None:
        values["oem"] = oem
    if app_id is not None:
        values["app_id"] = app_id
    if client_type is not None:
        values["client_type"] = client_type
    if ca_path is not None:
        values["ca_path"] = optional_config_path(ca_path)
    if cert_path is not None:
        values["cert_path"] = optional_config_path(cert_path)
    if key_path is not None:
        values["key_path"] = optional_config_path(key_path)
    if ip_region_id is not None:
        values["ip_region_id"] = ip_region_id
    if live_play_payload is not None:
        values["live_play_payload"] = live_play_payload
    if live_inner is not None:
        values["live_inner"] = bool(live_inner)
    if live_newcn is not None:
        values["live_newcn"] = bool(live_newcn)
    if live_keepalive_interval is not None:
        values["live_keepalive_interval"] = non_negative_float(
            live_keepalive_interval,
            field_name="live_keepalive_interval",
        )
    if play_sync_iterations is not None:
        values["play_sync_iterations"] = non_negative_value(
            play_sync_iterations,
            field_name="play_sync_iterations",
        )
    if enable_play_probes is not None:
        values["enable_play_probes"] = bool(enable_play_probes)
    if tls_verify is not None:
        values["tls_verify"] = bool(tls_verify)
    if channel is not None:
        values["channel"] = channel
    if stream is not None:
        values["stream"] = resolve_stream_quality(stream)
    if stream_quality is not None:
        values["stream"] = resolve_stream_quality(stream_quality)
    return replace(config, **cast(Any, values))
