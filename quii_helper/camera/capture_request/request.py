import math
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, cast

from quii_helper.camera.capture_request.request_state import (
    capture_settings_overrides,
    normalized_duration_seconds,
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
    warmup_seconds: float | None = None,
) -> PreviewCaptureSettings:
    duration = normalized_duration_seconds(
        preview_settings.capture_seconds
        if duration_seconds is None
        else duration_seconds
    )
    values = capture_settings_overrides(
        duration_seconds=duration_seconds,
        save_diagnostic_artifacts=save_diagnostic_artifacts,
        stop_when_decodable=stop_when_decodable,
    )
    warmup = (
        preview_settings.snapshot_warmup_seconds
        if warmup_seconds is None
        else warmup_seconds
    )
    if (
        isinstance(warmup, bool)
        or not isinstance(warmup, (int, float))
        or not math.isfinite(warmup)
        or not 0 <= warmup < duration
    ):
        raise ValueError(
            "warmup_seconds must be finite, nonnegative and less than the capture timeout"
        )
    if warmup_seconds is not None:
        values["snapshot_warmup_seconds"] = float(warmup)
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
    warmup_seconds: float | None = None,
) -> CameraCaptureRequest:
    settings = resolve_capture_settings(
        preview_settings,
        duration_seconds=duration_seconds,
        save_diagnostic_artifacts=save_diagnostic_artifacts,
        stop_when_decodable=stop_when_decodable,
        warmup_seconds=warmup_seconds,
    )
    if settings.snapshot_warmup_seconds and not render_snapshot:
        raise ValueError("warmup_seconds requires render_snapshot=True")
    return CameraCaptureRequest(
        settings=settings,
        output_base=output_base_from_path(output_path),
        render_snapshot=render_snapshot,
        render_video=render_video,
    )
