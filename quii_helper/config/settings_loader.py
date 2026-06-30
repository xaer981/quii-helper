import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from threading import Lock

from dotenv import load_dotenv

from quii_helper.support.errors import ConfigurationError

_DEFAULT_SETTINGS: "EnvironmentSettings | None" = None
_DEFAULT_SETTINGS_LOCK = Lock()


@dataclass(frozen=True)
class EnvironmentSettings:
    project_root: Path
    default_assets_dir: Path
    default_native_lib_dir: Path
    cloud_account: str
    cloud_password: str
    device_id: str
    auth_code: str
    device_password: str
    cloud_client_uuid: str
    log_level: str
    cloud_auth_version: str
    cloud_auth_url: str
    cloud_service_url: str
    camera_oem: str
    camera_app_id: int
    camera_client_type: int
    ip_region_id: int
    tls_ca_path: Path
    tls_cert_path: Path
    tls_key_path: Path
    p2p_so_paths: tuple[Path, Path]
    camera_channel: int
    camera_stream: int
    tls_verify: bool


class SettingsLoader:
    """Load project settings from `.env` and process environment values."""

    def __init__(
        self,
        *,
        project_root: Path | None = None,
        env: Mapping[str, str] | None = None,
        load_env_file: bool = True,
    ) -> None:
        self.project_root = project_root or self.default_project_root()
        self.env = env
        self.load_env_file = load_env_file

    @staticmethod
    def default_project_root() -> Path:
        return Path(__file__).resolve().parents[2]

    def load(self) -> EnvironmentSettings:
        if self.load_env_file and self.env is None:
            load_dotenv(self.project_root / ".env")

        assets_dir = self.project_root / "assets"
        native_lib_dir = assets_dir / "lib"
        return EnvironmentSettings(
            project_root=self.project_root,
            default_assets_dir=assets_dir,
            default_native_lib_dir=native_lib_dir,
            cloud_account=self.getenv("CLOUD_USERNAME", "CLOUD_ACCOUNT"),
            cloud_password=self.getenv("CLOUD_PASSWORD"),
            device_id=self.getenv("DEVICE_ID"),
            auth_code=self.getenv("AUTH_CODE"),
            device_password=self.getenv("DEVICE_PASSWORD"),
            cloud_client_uuid=self.getenv("CLOUD_CLIENT_UUID"),
            log_level=self.getenv("LOG_LEVEL", default="INFO"),
            cloud_auth_version=self.getenv("CLOUD_AUTH_VERSION"),
            cloud_auth_url=self.getenv("CLOUD_AUTH_URL"),
            cloud_service_url=self.getenv("CLOUD_SERVICE_URL"),
            camera_oem=self.getenv("CAMERA_OEM", "CLOUD_OEM"),
            camera_app_id=self.getenv_int(
                "CAMERA_APP_ID",
                "CLOUD_APP_ID",
                default=0,
            ),
            camera_client_type=self.getenv_int(
                "CAMERA_CLIENT_TYPE",
                "CLOUD_CLIENT_TYPE",
                default=0,
            ),
            ip_region_id=self.getenv_int("IP_REGION_ID", default=0),
            tls_ca_path=assets_dir / "ca.pem",
            tls_cert_path=assets_dir / "client.pem",
            tls_key_path=assets_dir / "client.txt",
            p2p_so_paths=(
                assets_dir / "libqv-p2p-v2.so",
                native_lib_dir / "arm64-v8a" / "libqv-p2p-v2.so",
            ),
            camera_channel=self.getenv_int(
                "CAMERA_CHANNEL",
                "VIDEO_PANEL",
                "QUII_CHANNEL",
                default=1,
            ),
            camera_stream=self.getenv_int(
                "CAMERA_STREAM",
                "QUII_STREAM",
                default=2,
            ),
            tls_verify=self.getenv_bool(
                "TLS_VERIFY",
                "CLOUD_TLS_VERIFY",
                default=True,
            ),
        )

    def getenv(self, *names: str, default: str = "") -> str:
        for name in names:
            value = self.env_value(name)
            if value is not None and value.strip():
                return value
        return default

    def getenv_int(self, *names: str, default: int) -> int:
        for name in names:
            value = self.env_value(name)
            if value is None or not value.strip():
                continue
            try:
                return int(value)
            except ValueError as exc:
                joined_names = ", ".join(names)
                raise ConfigurationError(
                    f"{name} must be an integer; checked {joined_names}"
                ) from exc
        return default

    def getenv_bool(self, *names: str, default: bool) -> bool:
        for name in names:
            value = self.env_value(name)
            if value is None or not value.strip():
                continue
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on"}:
                return True
            if normalized in {"0", "false", "no", "off"}:
                return False
            joined_names = ", ".join(names)
            raise ConfigurationError(
                f"{name} must be a boolean; checked {joined_names}"
            )
        return default

    def env_value(self, name: str) -> str | None:
        if self.env is not None:
            return self.env.get(name)
        return os.getenv(name)


def load_environment_settings(
    *,
    project_root: Path | None = None,
    env: Mapping[str, str] | None = None,
    load_env_file: bool = True,
) -> EnvironmentSettings:
    """Load settings using an explicit loader configuration."""

    return SettingsLoader(
        project_root=project_root,
        env=env,
        load_env_file=load_env_file,
    ).load()


def get_default_settings() -> EnvironmentSettings:
    """Return cached settings for the default project `.env`."""

    global _DEFAULT_SETTINGS

    if _DEFAULT_SETTINGS is not None:
        return _DEFAULT_SETTINGS

    with _DEFAULT_SETTINGS_LOCK:
        if _DEFAULT_SETTINGS is None:
            _DEFAULT_SETTINGS = load_environment_settings()
        return _DEFAULT_SETTINGS


def reset_default_settings_cache() -> None:
    """Clear the default settings cache.

    This is primarily useful for tests that need deterministic environment
    isolation.
    """

    global _DEFAULT_SETTINGS

    with _DEFAULT_SETTINGS_LOCK:
        _DEFAULT_SETTINGS = None


def has_default_settings_cache() -> bool:
    """Return whether default settings have already been loaded."""

    return _DEFAULT_SETTINGS is not None
