from dataclasses import replace
from typing import Any, cast

from quii_helper.config import AutonomousConfig
from quii_helper.support.errors import ConfigurationError


def resolve_runtime_config(
    config: AutonomousConfig | str | None,
    *,
    device_id: str | None,
    cloud_username: str | None,
    cloud_account: str | None,
    cloud_password: str | None,
    client_id: str | None,
    auth_url: str | None,
    service_url: str | None,
    oem: str | None,
    app_id: int | None,
    client_type: int | None,
    ip_region_id: int | None,
    tls_verify: bool | None = None,
) -> AutonomousConfig:
    if isinstance(config, AutonomousConfig):
        resolved = config
    else:
        resolved = (
            AutonomousConfig(device_id=config)
            if isinstance(config, str)
            else AutonomousConfig()
        )

    if (
        cloud_username is not None
        and cloud_account is not None
        and cloud_username != cloud_account
    ):
        raise ConfigurationError(
            "pass either cloud_username or cloud_account, not both"
        )

    values = {
        key: value
        for key, value in {
            "device_id": device_id,
            "cloud_account": cloud_username or cloud_account,
            "cloud_password": cloud_password,
            "client_id": client_id,
            "auth_url": auth_url,
            "service_url": service_url,
            "oem": oem,
            "app_id": app_id,
            "client_type": client_type,
            "ip_region_id": ip_region_id,
            "tls_verify": tls_verify,
        }.items()
        if value is not None
    }
    return replace(resolved, **cast(Any, values)) if values else resolved


def validate_runtime_config(config: AutonomousConfig) -> None:
    missing = [
        name
        for name, value in {
            "device_id": config.device_id,
            "cloud_account": config.cloud_account,
            "cloud_password": config.cloud_password,
        }.items()
        if not value
    ]
    if missing:
        raise ConfigurationError(
            f"missing required camera credentials: {', '.join(missing)}"
        )
