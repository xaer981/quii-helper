from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, cast

from quii_helper.camera.capture_request.request_state import (
    capture_settings_overrides,
)
from quii_helper.camera.outputs.paths import output_base_from_path
from quii_helper.preview.pipeline.config import PreviewCaptureSettings


@dataclass(frozen=True)
class CameraCaptureRequest:
    settings: PreviewCaptureSettings
    output_base: Path | None
    render_snapshot: bool
    render_video: bool


def resolve_capture_settings(
    preview_settings: PreviewCaptureSettings,
    *,
    duration_seconds: float | None,
    save_diagnostic_artifacts: bool | None,
    stop_when_decodable: bool | None,
) -> PreviewCaptureSettings:
    values = capture_settings_overrides(
        duration_seconds=duration_seconds,
        save_diagnostic_artifacts=save_diagnostic_artifacts,
        stop_when_decodable=stop_when_decodable,
    )
    return (
        replace(preview_settings, **cast(Any, values))
        if values
        else preview_settings
    )


def resolve_capture_request(
    preview_settings: PreviewCaptureSettings,
    *,
    duration_seconds: float | None,
    output_path: str | Path | None,
    save_diagnostic_artifacts: bool | None,
    stop_when_decodable: bool | None,
    render_snapshot: bool,
    render_video: bool,
) -> CameraCaptureRequest:
    return CameraCaptureRequest(
        settings=resolve_capture_settings(
            preview_settings,
            duration_seconds=duration_seconds,
            save_diagnostic_artifacts=save_diagnostic_artifacts,
            stop_when_decodable=stop_when_decodable,
        ),
        output_base=output_base_from_path(output_path),
        render_snapshot=render_snapshot,
        render_video=render_video,
    )
