STREAM_HIGH_QUALITY = 1
STREAM_LOW_BANDWIDTH = 2

STREAM_QUALITY_ALIASES = {
    "high": STREAM_HIGH_QUALITY,
    "main": STREAM_HIGH_QUALITY,
    "hd": STREAM_HIGH_QUALITY,
    "clear": STREAM_HIGH_QUALITY,
    "low": STREAM_LOW_BANDWIDTH,
    "sub": STREAM_LOW_BANDWIDTH,
    "sd": STREAM_LOW_BANDWIDTH,
    "smooth": STREAM_LOW_BANDWIDTH,
}

REQUIRED_CAMERA_APP_FIELDS = {
    "service_url": "CLOUD_SERVICE_URL",
    "auth_url": "CLOUD_AUTH_URL",
    "oem": "CAMERA_OEM",
    "app_id": "CAMERA_APP_ID",
    "client_type": "CAMERA_CLIENT_TYPE",
    "client_id": "CLOUD_CLIENT_UUID",
    "ip_region_id": "IP_REGION_ID",
}


def resolve_stream_quality(value: str | int) -> int:
    if isinstance(value, bool):
        raise ValueError("stream quality must be a stream id or profile name")
    if isinstance(value, int):
        stream = value
    else:
        key = value.strip().lower().replace("-", "_")
        try:
            stream = STREAM_QUALITY_ALIASES[key]
        except KeyError as exc:
            names = ", ".join(sorted(STREAM_QUALITY_ALIASES))
            raise ValueError(
                f"unknown stream quality {value!r}; expected one of: {names}"
            ) from exc
    if stream <= 0:
        raise ValueError("stream id must be greater than zero")
    return stream


def validate_camera_app_config(config: object) -> None:
    missing = missing_camera_app_fields(config)
    if missing:
        raise ValueError(
            "missing required app-specific camera configuration: "
            f"{', '.join(missing)}. "
            "Extract these values from the decompiled vendor app and put "
            "them in .env, or pass them explicitly to Camera(...)."
        )


def missing_camera_app_fields(config: object) -> list[str]:
    return [
        f"{field} ({env_name})"
        for field, env_name in REQUIRED_CAMERA_APP_FIELDS.items()
        if is_missing_config_value(getattr(config, field))
    ]


def is_missing_config_value(value: object) -> bool:
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, int):
        return value <= 0
    return value is None
