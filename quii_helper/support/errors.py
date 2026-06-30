class QuiiHelperError(Exception):
    """Base class for QUII helper domain errors."""


class ConfigurationError(ValueError, QuiiHelperError):
    """Raised when user or application configuration is invalid."""


class AssetMissingError(FileNotFoundError, QuiiHelperError):
    """Raised when a required local asset is missing or unusable."""


class QuiiConnectionError(OSError, QuiiHelperError):
    """Raised when cloud, P2P, or device connection setup fails."""


ConnectionError = QuiiConnectionError


class CameraCaptureError(RuntimeError, QuiiHelperError):
    """Raised when a requested media artifact could not be produced."""


class MediaRenderError(CameraCaptureError):
    """Raised when captured media cannot be rendered to the requested output."""
