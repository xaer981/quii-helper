import pytest

from quii_helper.config import (
    REQUIRED_CAMERA_APP_FIELDS,
    STREAM_HIGH_QUALITY,
    STREAM_LOW_BANDWIDTH,
    STREAM_QUALITY_ALIASES,
    AutonomousConfig,
    resolve_stream_quality,
    validate_camera_app_config,
)
from quii_helper.config import validation as config_validation


class ConfigTests:
    def test_resolve_stream_quality_aliases(self) -> None:
        assert STREAM_HIGH_QUALITY == resolve_stream_quality("high")
        assert STREAM_HIGH_QUALITY == resolve_stream_quality("main")
        assert STREAM_HIGH_QUALITY == resolve_stream_quality("clear")
        assert STREAM_HIGH_QUALITY == resolve_stream_quality("HD")
        assert STREAM_LOW_BANDWIDTH == resolve_stream_quality("low")
        assert STREAM_LOW_BANDWIDTH == resolve_stream_quality("sub")
        assert STREAM_LOW_BANDWIDTH == resolve_stream_quality("sd")
        assert STREAM_LOW_BANDWIDTH == (resolve_stream_quality("smooth"))
        assert 3 == resolve_stream_quality(3)

    def test_resolve_stream_quality_rejects_invalid_values(self) -> None:
        with pytest.raises(ValueError):
            resolve_stream_quality(True)
        with pytest.raises(ValueError):
            resolve_stream_quality(0)
        with pytest.raises(ValueError):
            resolve_stream_quality("unknown")

    def test_validate_camera_app_config_accepts_complete_values(self) -> None:
        config = AutonomousConfig(
            service_url="https://service.example",
            auth_url="https://auth.example",
            oem="OEM",
            app_id=1,
            client_type=2,
            client_id="client-id",
            ip_region_id=3,
        )

        validate_camera_app_config(config)

    def test_validate_camera_app_config_reports_missing_values(self) -> None:
        config = AutonomousConfig(
            service_url="",
            auth_url="",
            oem="",
            app_id=0,
            client_type=0,
            client_id="",
            ip_region_id=0,
        )

        with pytest.raises(
            ValueError, match="CLOUD_SERVICE_URL.*CLOUD_AUTH_URL.*CAMERA_OEM"
        ):
            validate_camera_app_config(config)

    def test_config_reexports_validation_constants(self) -> None:
        assert config_validation.STREAM_QUALITY_ALIASES is (
            STREAM_QUALITY_ALIASES
        )
        assert config_validation.REQUIRED_CAMERA_APP_FIELDS is (
            REQUIRED_CAMERA_APP_FIELDS
        )
