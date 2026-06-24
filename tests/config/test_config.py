import unittest

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


class ConfigTests(unittest.TestCase):
    def test_resolve_stream_quality_aliases(self) -> None:
        self.assertEqual(STREAM_HIGH_QUALITY, resolve_stream_quality("high"))
        self.assertEqual(STREAM_HIGH_QUALITY, resolve_stream_quality("main"))
        self.assertEqual(STREAM_HIGH_QUALITY, resolve_stream_quality("clear"))
        self.assertEqual(STREAM_HIGH_QUALITY, resolve_stream_quality("HD"))
        self.assertEqual(STREAM_LOW_BANDWIDTH, resolve_stream_quality("low"))
        self.assertEqual(STREAM_LOW_BANDWIDTH, resolve_stream_quality("sub"))
        self.assertEqual(STREAM_LOW_BANDWIDTH, resolve_stream_quality("sd"))
        self.assertEqual(
            STREAM_LOW_BANDWIDTH,
            resolve_stream_quality("smooth"),
        )
        self.assertEqual(3, resolve_stream_quality(3))

    def test_resolve_stream_quality_rejects_invalid_values(self) -> None:
        with self.assertRaises(ValueError):
            resolve_stream_quality(True)
        with self.assertRaises(ValueError):
            resolve_stream_quality(0)
        with self.assertRaises(ValueError):
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

        with self.assertRaisesRegex(
            ValueError,
            "CLOUD_SERVICE_URL.*CLOUD_AUTH_URL.*CAMERA_OEM",
        ):
            validate_camera_app_config(config)

    def test_config_reexports_validation_constants(self) -> None:
        self.assertIs(
            config_validation.STREAM_QUALITY_ALIASES,
            STREAM_QUALITY_ALIASES,
        )
        self.assertIs(
            config_validation.REQUIRED_CAMERA_APP_FIELDS,
            REQUIRED_CAMERA_APP_FIELDS,
        )


if __name__ == "__main__":
    unittest.main()
