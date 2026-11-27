"""Value-free configuration diagnostics shared by installed commands."""

from quii_helper.config import AutonomousConfig
from quii_helper.config.settings_loader import (
    CHANNEL_SETTINGS,
    STREAM_SETTINGS,
    SettingsLoader,
)
from quii_helper.support.errors import ConfigurationError


class _PreflightError(ValueError):
    """An error whose message is safe to display on the CLI."""


def _setting_problem(
    loader: SettingsLoader, error: ConfigurationError, *, scope: str = "LAN"
) -> str:
    """Explain an invalid setting without exposing its configured value."""
    if not error.setting or not error.hint:
        return f"Check {scope} settings in .env and the process environment."
    names = {
        CHANNEL_SETTINGS[0]: CHANNEL_SETTINGS,
        STREAM_SETTINGS[0]: STREAM_SETTINGS,
        "CLOUD_ACCOUNT": ("CLOUD_ACCOUNT", "CLOUD_USERNAME"),
        "CAMERA_OEM": ("CAMERA_OEM", "CLOUD_OEM"),
        "CAMERA_APP_ID": ("CAMERA_APP_ID", "CLOUD_APP_ID"),
        "CAMERA_CLIENT_TYPE": ("CAMERA_CLIENT_TYPE", "CLOUD_CLIENT_TYPE"),
    }.get(error.setting, (error.setting,))
    name, source = loader.setting_origin(*names)
    if source == "not set":
        for alias in names[1:]:
            alias_name, alias_source = loader.setting_origin(alias)
            if alias_source != "not set":
                name, source = alias_name, alias_source
                break
    return f"{name} ({source}): {error.hint}"


def _load_cli_config(
    *, scope: str = "LAN"
) -> tuple[AutonomousConfig, SettingsLoader]:
    """Load explicit CLI settings with safe errors, without network I/O."""
    try:
        loader = SettingsLoader()
    except (OSError, ValueError):
        raise _PreflightError(
            "Cannot resolve the application directory."
        ) from None
    try:
        config = AutonomousConfig.from_settings(loader.load())
    except ConfigurationError as exc:
        raise _PreflightError(
            _setting_problem(loader, exc, scope=scope)
        ) from None
    except (OSError, ValueError):
        raise _PreflightError(
            "Cannot load configuration. Check that .env is readable UTF-8."
        ) from None
    return config, loader
