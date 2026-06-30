from typing import Any

from quii_helper.config.settings_loader import get_default_settings

_SETTING_EXPORTS = {
    "PROJECT_ROOT": "project_root",
    "DEFAULT_ASSETS_DIR": "default_assets_dir",
    "DEFAULT_NATIVE_LIB_DIR": "default_native_lib_dir",
    "CLOUD_ACCOUNT": "cloud_account",
    "CLOUD_PASSWORD": "cloud_password",
    "DEVICE_ID": "device_id",
    "AUTH_CODE": "auth_code",
    "DEVICE_PASSWORD": "device_password",
    "CLOUD_CLIENT_UUID": "cloud_client_uuid",
    "LOG_LEVEL": "log_level",
    "CLOUD_AUTH_VERSION": "cloud_auth_version",
    "CLOUD_AUTH_URL": "cloud_auth_url",
    "CLOUD_SERVICE_URL": "cloud_service_url",
    "CAMERA_OEM": "camera_oem",
    "CAMERA_APP_ID": "camera_app_id",
    "CAMERA_CLIENT_TYPE": "camera_client_type",
    "IP_REGION_ID": "ip_region_id",
    "TLS_CA_PATH": "tls_ca_path",
    "TLS_CERT_PATH": "tls_cert_path",
    "TLS_KEY_PATH": "tls_key_path",
    "P2P_SO_PATHS": "p2p_so_paths",
    "CAMERA_CHANNEL": "camera_channel",
    "CAMERA_STREAM": "camera_stream",
    "TLS_VERIFY": "tls_verify",
}

__all__ = tuple(_SETTING_EXPORTS)


def __getattr__(name: str) -> Any:
    """Resolve legacy constants lazily from default settings."""

    setting_name = _SETTING_EXPORTS.get(name)
    if setting_name is None:
        raise AttributeError(name)
    return getattr(get_default_settings(), setting_name)
