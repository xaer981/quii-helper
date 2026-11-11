"""Connection policy shared by configuration and the camera API."""

from quii_helper.support.errors import ConfigurationError


def validate_connection_options(mode: str, port: int) -> None:
    """Reject ambiguous modes and invalid native TCP ports without I/O."""
    if mode not in {"lan", "cloud"}:
        raise ConfigurationError.for_setting(
            "CAMERA_CONNECTION_MODE",
            "Set it to lan for this check.",
            message="connection_mode must be 'lan' or 'cloud'",
        )
    if (
        isinstance(port, bool)
        or not isinstance(port, int)
        or not 1 <= port <= 65535
    ):
        raise ConfigurationError.for_setting(
            "CAMERA_STREAM_PORT",
            "Use a port from 1 to 65535.",
            message="stream_port must be an integer from 1 to 65535",
        )


def require_cloud_connection(mode: str, *, operation: str) -> None:
    """Require explicit opt-in before a Camera operation can use the cloud."""
    if mode != "cloud":
        raise ConfigurationError(
            f"{operation} requires connection_mode='cloud'; "
            "cloud access is disabled in LAN-only mode"
        )
