import tempfile
from pathlib import Path

import pytest

from quii_helper.protocols.ust.crypto_tables import load_p2p_crypto_tables
from quii_helper.support.errors import (
    AssetMissingError,
    CameraCaptureError,
    ConfigurationError,
    MediaRenderError,
    QuiiConnectionError,
    QuiiHelperError,
)


class ErrorHierarchyTests:
    def test_camera_capture_error_preserves_runtime_error_compatibility(
        self,
    ) -> None:
        assert issubclass(CameraCaptureError, RuntimeError)
        assert issubclass(CameraCaptureError, QuiiHelperError)

    def test_configuration_error_preserves_value_error_compatibility(
        self,
    ) -> None:
        assert issubclass(ConfigurationError, ValueError)
        assert issubclass(ConfigurationError, QuiiHelperError)

    def test_asset_missing_error_preserves_file_not_found_compatibility(
        self,
    ) -> None:
        assert issubclass(AssetMissingError, FileNotFoundError)
        assert issubclass(AssetMissingError, QuiiHelperError)

    def test_connection_error_preserves_os_error_compatibility(self) -> None:
        assert issubclass(QuiiConnectionError, OSError)
        assert issubclass(QuiiConnectionError, QuiiHelperError)

    def test_media_render_error_preserves_runtime_error_compatibility(
        self,
    ) -> None:
        assert issubclass(MediaRenderError, RuntimeError)
        assert issubclass(MediaRenderError, CameraCaptureError)
        assert issubclass(MediaRenderError, QuiiHelperError)

    def test_missing_p2p_crypto_table_asset_raises_domain_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing_path = Path(tmp) / "libqv-p2p-v2.so"

            with pytest.raises(AssetMissingError):
                load_p2p_crypto_tables(missing_path)
