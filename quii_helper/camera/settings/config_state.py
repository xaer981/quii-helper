from pathlib import Path


def validate_stream_selector(
    *, stream: int | None, stream_quality: str | int | None
) -> None:
    if stream is not None and stream_quality is not None:
        raise ValueError("pass either stream or stream_quality, not both")


def resolve_cloud_account_alias(
    *, cloud_username: str | None, cloud_account: str | None
) -> str | None:
    if (
        cloud_username is not None
        and cloud_account is not None
        and cloud_username != cloud_account
    ):
        raise ValueError(
            "pass either cloud_username or cloud_account, not both"
        )
    return cloud_username or cloud_account


def optional_config_path(path: str | Path | None) -> Path | None:
    if path is None:
        return None
    return Path(path)


def non_negative_float(value: float, *, field_name: str) -> float:
    if value < 0:
        raise ValueError(f"{field_name} must be zero or greater")
    return float(value)


def non_negative_value(value: int, *, field_name: str) -> int:
    if value < 0:
        raise ValueError(f"{field_name} must be zero or greater")
    return value
