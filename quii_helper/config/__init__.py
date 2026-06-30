from quii_helper.config import validation
from quii_helper.config.models import (
    DEFAULT_SERVICE_QUERY_PATH,
    AutonomousConfig,
    RuntimeCredentials,
    ServiceEntry,
    ServiceQueryResponse,
    load_config,
)
from quii_helper.config.settings_loader import (
    EnvironmentSettings,
    get_default_settings,
    load_environment_settings,
)

STREAM_HIGH_QUALITY = validation.STREAM_HIGH_QUALITY
STREAM_LOW_BANDWIDTH = validation.STREAM_LOW_BANDWIDTH
STREAM_QUALITY_ALIASES = validation.STREAM_QUALITY_ALIASES
REQUIRED_CAMERA_APP_FIELDS = validation.REQUIRED_CAMERA_APP_FIELDS
resolve_stream_quality = validation.resolve_stream_quality
validate_camera_app_config = validation.validate_camera_app_config

_DEFAULT_SETTING_EXPORTS = {
    "DEFAULT_SERVICE_URL": "cloud_service_url",
    "DEFAULT_AUTH_URL": "cloud_auth_url",
    "DEFAULT_OEM": "camera_oem",
    "DEFAULT_APP_ID": "camera_app_id",
    "DEFAULT_CLIENT_TYPE": "camera_client_type",
    "DEFAULT_CHANNEL": "camera_channel",
    "DEFAULT_STREAM": "camera_stream",
}


def __getattr__(name: str) -> object:
    setting_name = _DEFAULT_SETTING_EXPORTS.get(name)
    if setting_name is None:
        raise AttributeError(name)
    return getattr(get_default_settings(), setting_name)


__all__ = [
    "DEFAULT_SERVICE_QUERY_PATH",
    "EnvironmentSettings",
    "AutonomousConfig",
    "RuntimeCredentials",
    "ServiceEntry",
    "ServiceQueryResponse",
    "STREAM_HIGH_QUALITY",
    "STREAM_LOW_BANDWIDTH",
    "STREAM_QUALITY_ALIASES",
    "REQUIRED_CAMERA_APP_FIELDS",
    "get_default_settings",
    "load_config",
    "load_environment_settings",
    "resolve_stream_quality",
    "validate_camera_app_config",
    "validation",
]
