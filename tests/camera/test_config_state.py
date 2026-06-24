import unittest
from pathlib import Path

from quii_helper.camera.settings.config_state import (
    non_negative_float,
    non_negative_value,
    optional_config_path,
    resolve_cloud_account_alias,
    validate_stream_selector,
)


class CameraConfigStateTests(unittest.TestCase):
    def test_validate_stream_selector_rejects_ambiguous_inputs(self) -> None:
        with self.assertRaises(ValueError):
            validate_stream_selector(stream=1, stream_quality="high")

        validate_stream_selector(stream=1, stream_quality=None)
        validate_stream_selector(stream=None, stream_quality="high")

    def test_resolve_cloud_account_alias_preserves_existing_alias_rules(
        self,
    ) -> None:
        self.assertEqual(
            "username",
            resolve_cloud_account_alias(
                cloud_username="username",
                cloud_account=None,
            ),
        )
        self.assertEqual(
            "account",
            resolve_cloud_account_alias(
                cloud_username=None,
                cloud_account="account",
            ),
        )
        self.assertEqual(
            "same",
            resolve_cloud_account_alias(
                cloud_username="same",
                cloud_account="same",
            ),
        )
        with self.assertRaises(ValueError):
            resolve_cloud_account_alias(
                cloud_username="a",
                cloud_account="b",
            )

    def test_optional_config_path_coerces_only_present_values(self) -> None:
        self.assertIsNone(optional_config_path(None))
        self.assertEqual(Path("cert.pem"), optional_config_path("cert.pem"))
        self.assertEqual(
            Path("key.pem"),
            optional_config_path(Path("key.pem")),
        )

    def test_non_negative_float_preserves_cast_and_error_message(self) -> None:
        self.assertEqual(
            1.5,
            non_negative_float(
                1.5,
                field_name="live_keepalive_interval",
            ),
        )
        with self.assertRaisesRegex(
            ValueError,
            "live_keepalive_interval must be zero or greater",
        ):
            non_negative_float(
                -1,
                field_name="live_keepalive_interval",
            )

    def test_non_negative_value_preserves_int_value(self) -> None:
        self.assertEqual(
            3,
            non_negative_value(3, field_name="play_sync_iterations"),
        )
        with self.assertRaisesRegex(
            ValueError,
            "play_sync_iterations must be zero or greater",
        ):
            non_negative_value(-1, field_name="play_sync_iterations")


if __name__ == "__main__":
    unittest.main()
