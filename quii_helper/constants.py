import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]

load_dotenv(PROJECT_ROOT / ".env")


def _getenv(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name)
        if value is not None and value.strip():
            return value
    return default


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


DEFAULT_ASSETS_DIR = PROJECT_ROOT / "assets"
DEFAULT_NATIVE_LIB_DIR = DEFAULT_ASSETS_DIR / "lib"

CLOUD_ACCOUNT = _getenv("CLOUD_USERNAME", "CLOUD_ACCOUNT")
CLOUD_PASSWORD = _getenv("CLOUD_PASSWORD")
DEVICE_ID = _getenv("DEVICE_ID")
AUTH_CODE = _getenv("AUTH_CODE")
DEVICE_PASSWORD = _getenv("DEVICE_PASSWORD")
CLOUD_CLIENT_UUID = _getenv("CLOUD_CLIENT_UUID")
LOG_LEVEL = _getenv("LOG_LEVEL", default="INFO")
CLOUD_AUTH_VERSION = _getenv("CLOUD_AUTH_VERSION")
CLOUD_AUTH_URL = _getenv("CLOUD_AUTH_URL")
CLOUD_SERVICE_URL = _getenv("CLOUD_SERVICE_URL")
CAMERA_OEM = _getenv("CAMERA_OEM", "CLOUD_OEM")
CAMERA_APP_ID = _getenv_int("CAMERA_APP_ID", "CLOUD_APP_ID", default=0)
CAMERA_CLIENT_TYPE = _getenv_int(
    "CAMERA_CLIENT_TYPE",
    "CLOUD_CLIENT_TYPE",
    default=0,
)
IP_REGION_ID = _getenv_int("IP_REGION_ID", default=0)
TLS_CA_PATH = DEFAULT_ASSETS_DIR / "ca.pem"
TLS_CERT_PATH = DEFAULT_ASSETS_DIR / "client.pem"
TLS_KEY_PATH = DEFAULT_ASSETS_DIR / "client.txt"
P2P_SO_PATHS = (
    DEFAULT_ASSETS_DIR / "libqv-p2p-v2.so",
    DEFAULT_NATIVE_LIB_DIR / "arm64-v8a" / "libqv-p2p-v2.so",
)
CAMERA_CHANNEL = _getenv_int(
    "CAMERA_CHANNEL",
    "VIDEO_PANEL",
    "QUII_CHANNEL",
    default=1,
)
CAMERA_STREAM = _getenv_int("CAMERA_STREAM", "QUII_STREAM", default=2)
