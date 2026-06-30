from pathlib import Path

import pytest

from quii_helper.camera.settings.config_state import (
    non_negative_float,
    non_negative_value,
    optional_config_path,
    resolve_cloud_account_alias,
    validate_stream_selector,
)


class CameraConfigStateTests:
    def test_validate_stream_selector_rejects_ambiguous_inputs(self) -> None:
        with pytest.raises(ValueError):
            validate_stream_selector(stream=1, stream_quality="high")

        validate_stream_selector(stream=1, stream_quality=None)
        validate_stream_selector(stream=None, stream_quality="high")

    def test_resolve_cloud_account_alias_preserves_existing_alias_rules(
        self,
    ) -> None:
        assert "username" == (
            resolve_cloud_account_alias(
                cloud_username="username",
                cloud_account=None,
            )
        )
        assert "account" == (
            resolve_cloud_account_alias(
                cloud_username=None,
                cloud_account="account",
            )
        )
        assert "same" == (
            resolve_cloud_account_alias(
                cloud_username="same",
                cloud_account="same",
            )
        )
        with pytest.raises(ValueError):
            resolve_cloud_account_alias(
                cloud_username="a",
                cloud_account="b",
            )

    def test_optional_config_path_coerces_only_present_values(self) -> None:
        assert optional_config_path(None) is None
        assert Path("cert.pem") == optional_config_path("cert.pem")
        assert Path("key.pem") == (optional_config_path(Path("key.pem")))

    def test_non_negative_float_preserves_cast_and_error_message(self) -> None:
        assert 1.5 == (
            non_negative_float(
                1.5,
                field_name="live_keepalive_interval",
            )
        )
        with pytest.raises(
            ValueError, match="live_keepalive_interval must be zero or greater"
        ):
            non_negative_float(
                -1,
                field_name="live_keepalive_interval",
            )

    def test_non_negative_value_preserves_int_value(self) -> None:
        assert 3 == (non_negative_value(3, field_name="play_sync_iterations"))
        with pytest.raises(
            ValueError, match="play_sync_iterations must be zero or greater"
        ):
            non_negative_value(-1, field_name="play_sync_iterations")
