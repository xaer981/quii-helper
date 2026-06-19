import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]

load_dotenv(PROJECT_ROOT / ".env")


def _getenv_int(*names: str, default: int) -> int:
    for name in names:
        value = os.getenv(name)
        if value is None or not value.strip():
            continue
        try:
            return int(value)
        except ValueError as exc:
            joined_names = ", ".join(names)
            raise ValueError(
                f"{name} must be an integer; checked {joined_names}"
            ) from exc
    return default


CLOUD_ACCOUNT = os.getenv("CLOUD_ACCOUNT", "")
CLOUD_PASSWORD = os.getenv("CLOUD_PASSWORD", "")
DEVICE_ID = os.getenv("DEVICE_ID", "")
AUTH_CODE = os.getenv("AUTH_CODE", "")
DEVICE_PASSWORD = os.getenv("DEVICE_PASSWORD", "")
CLOUD_CLIENT_UUID = os.getenv("CLOUD_CLIENT_UUID", "")
CAMERA_CHANNEL = _getenv_int(
    "CAMERA_CHANNEL",
    "VIDEO_PANEL",
    "QUII_CHANNEL",
    default=1,
)
