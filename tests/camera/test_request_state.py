import unittest

from quii_helper.camera.capture_request.request_state import (
    capture_settings_overrides,
    normalized_duration_seconds,
)


class CameraRequestStateTests(unittest.TestCase):
    def test_normalized_duration_seconds_preserves_cast_and_validation(
        self,
    ) -> None:
        self.assertEqual(3.0, normalized_duration_seconds(3))
        self.assertEqual(3.5, normalized_duration_seconds(3.5))

        with self.assertRaisesRegex(
            ValueError, "duration_seconds must be greater than zero"
        ):
            normalized_duration_seconds(0)

    def test_capture_settings_overrides_skips_absent_values(self) -> None:
        self.assertEqual(
            {},
            capture_settings_overrides(
                duration_seconds=None,
                save_diagnostic_artifacts=None,
                stop_when_decodable=None,
            ),
        )

    def test_capture_settings_overrides_preserves_existing_keys(self) -> None:
        self.assertEqual(
            {
                "capture_seconds": 4.0,
                "save_diagnostic_artifacts": True,
                "stop_when_decodable": False,
            },
            capture_settings_overrides(
                duration_seconds=4,
                save_diagnostic_artifacts=1,
                stop_when_decodable=0,
            ),
        )


if __name__ == "__main__":
    unittest.main()
