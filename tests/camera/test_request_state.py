import pytest

from quii_helper.camera.capture_request.request import resolve_capture_settings
from quii_helper.camera.capture_request.request_state import (
    capture_settings_overrides,
    normalized_duration_seconds,
)
from quii_helper.preview.pipeline.config import PreviewCaptureSettings


class CameraRequestStateTests:
    @pytest.mark.parametrize("duration", [float("nan"), float("inf")])
    def test_invalid_duration_in_default_settings_is_rejected(self, duration):
        with pytest.raises(ValueError, match="finite"):
            resolve_capture_settings(
                PreviewCaptureSettings(capture_seconds=duration),
                duration_seconds=None,
                save_diagnostic_artifacts=None,
                stop_when_decodable=None,
            )

    @pytest.mark.parametrize(
        "duration", [float("nan"), float("inf"), -float("inf"), -1]
    )
    def test_non_finite_or_negative_duration_is_rejected(
        self, duration
    ) -> None:
        with pytest.raises(ValueError, match="greater than zero"):
            normalized_duration_seconds(duration)

    def test_normalized_duration_seconds_preserves_cast_and_validation(
        self,
    ) -> None:
        assert 3.0 == normalized_duration_seconds(3)
        assert 3.5 == normalized_duration_seconds(3.5)

        with pytest.raises(
            ValueError, match="duration_seconds must be greater than zero"
        ):
            normalized_duration_seconds(0)

    def test_capture_settings_overrides_skips_absent_values(self) -> None:
        assert {} == (
            capture_settings_overrides(
                duration_seconds=None,
                save_diagnostic_artifacts=None,
                stop_when_decodable=None,
            )
        )

    def test_capture_settings_overrides_preserves_existing_keys(self) -> None:
        assert {
            "capture_seconds": 4.0,
            "save_diagnostic_artifacts": True,
            "stop_when_decodable": False,
        } == (
            capture_settings_overrides(
                duration_seconds=4,
                save_diagnostic_artifacts=1,
                stop_when_decodable=0,
            )
        )
