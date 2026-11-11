class QuiiHelperError(Exception):
    """Base class for QUII helper domain errors."""


class ConfigurationError(ValueError, QuiiHelperError):
    """Raised when user or application configuration is invalid."""

    setting: str | None = None
    hint: str | None = None

    @classmethod
    def for_setting(
        cls, setting: str, hint: str, *, message: str | None = None
    ) -> "ConfigurationError":
        """Attach a value-free hint without changing the exception message."""
        error = cls(message if message is not None else hint)
        error.setting = setting
        error.hint = hint
        return error


class AssetMissingError(FileNotFoundError, QuiiHelperError):
    """Raised when a required local asset is missing or unusable."""


class QuiiConnectionError(OSError, QuiiHelperError):
    """Raised when cloud, P2P, or device connection setup fails."""


ConnectionError = QuiiConnectionError


class CameraCaptureError(RuntimeError, QuiiHelperError):
    """Raised when a requested media artifact could not be produced."""


class MediaRenderError(CameraCaptureError):
    """Raised when captured media cannot be rendered to the requested output."""


class AudioDeviceError(RuntimeError, QuiiHelperError):
    """Raised when local microphone/speaker initialization or streaming fails."""
