from collections.abc import Callable
from pathlib import Path

from quii_helper.camera.connection.session import (
    CameraConnector,
    CameraPreviewSession,
)
from quii_helper.camera.outputs.results import (
    CameraCaptureError,
    CameraCaptureResult,
)
from quii_helper.camera.runtime.capture import capture_preview_summary
from quii_helper.camera.settings.init_state import camera_config_kwargs
from quii_helper.camera.settings.options import (
    resolve_camera_config,
    resolve_capture_request,
    validate_output_path,
)
from quii_helper.config import AutonomousConfig
from quii_helper.io.paths import DATA_DIR
from quii_helper.preview.pipeline.config import (
    DEFAULT_PREVIEW_CAPTURE_SETTINGS,
    PreviewCaptureSettings,
)
from quii_helper.support.log import logger

EmitCallback = Callable[[object], None]
StatusCallback = Callable[[str], None]

__all__ = [
    "Camera",
    "CameraCaptureError",
    "CameraCaptureResult",
    "CameraConnector",
    "CameraPreviewSession",
]


def _default_emit(obj: object) -> None:
    logger.debug("{}", obj)


def _default_status(message: str) -> None:
    logger.info(message)


class Camera:
    def __init__(
        self,
        config: AutonomousConfig | None = None,
        *,
        device_id: str | None = None,
        cloud_username: str | None = None,
        cloud_account: str | None = None,
        cloud_password: str | None = None,
        client_id: str | None = None,
        service_url: str | None = None,
        auth_url: str | None = None,
        oem: str | None = None,
        app_id: int | None = None,
        client_type: int | None = None,
        ca_path: str | Path | None = None,
        cert_path: str | Path | None = None,
        key_path: str | Path | None = None,
        ip_region_id: int | None = None,
        live_play_payload: str | None = None,
        live_inner: bool | None = None,
        live_newcn: bool | None = None,
        live_keepalive_interval: float | None = None,
        play_sync_iterations: int | None = None,
        enable_play_probes: bool | None = None,
        channel: int | None = None,
        stream: int | None = None,
        stream_quality: str | int | None = None,
        preview_settings: PreviewCaptureSettings | None = None,
        data_dir: str | Path = DATA_DIR,
        emit: EmitCallback | None = None,
        status: StatusCallback | None = None,
    ) -> None:
        self.config = resolve_camera_config(
            config or AutonomousConfig(),
            **camera_config_kwargs(locals()),
        )
        self.preview_settings = (
            preview_settings or DEFAULT_PREVIEW_CAPTURE_SETTINGS
        )
        self.data_dir = Path(data_dir)
        self.emit = emit or _default_emit
        self.status = status or _default_status
        self.connector = CameraConnector(self.config)

    def capture(
        self,
        *,
        duration_seconds: float | None = None,
        output_path: str | Path | None = None,
        save_diagnostic_artifacts: bool | None = None,
        stop_when_decodable: bool | None = None,
        render_snapshot: bool = True,
        render_video: bool = True,
    ) -> CameraCaptureResult:
        request = resolve_capture_request(
            self.preview_settings,
            duration_seconds=duration_seconds,
            output_path=output_path,
            save_diagnostic_artifacts=save_diagnostic_artifacts,
            stop_when_decodable=stop_when_decodable,
            render_snapshot=render_snapshot,
            render_video=render_video,
        )
        summary = self._capture_summary(
            settings=request.settings,
            output_base=request.output_base,
            render_snapshot=request.render_snapshot,
            render_video=request.render_video,
        )
        return CameraCaptureResult.from_summary(summary)

    def snapshot(
        self,
        *,
        timeout_seconds: float = 5.0,
        output_path: str | Path | None = None,
    ) -> Path:
        result = self.capture(
            duration_seconds=timeout_seconds,
            output_path=validate_output_path(output_path, ".jpg"),
            stop_when_decodable=True,
            render_snapshot=True,
            render_video=False,
        )
        return result.require_snapshot()

    def save_video(
        self,
        duration_seconds: float,
        *,
        output_path: str | Path | None = None,
    ) -> Path:
        result = self.capture(
            duration_seconds=duration_seconds,
            output_path=validate_output_path(output_path, ".mp4"),
            stop_when_decodable=False,
            render_snapshot=False,
            render_video=True,
        )
        return result.require_video()

    def record(
        self,
        duration_seconds: float,
        *,
        output_path: str | Path | None = None,
    ) -> Path:
        return self.save_video(duration_seconds, output_path=output_path)

    def _capture_summary(
        self,
        *,
        settings: PreviewCaptureSettings,
        output_base: Path | None,
        render_snapshot: bool,
        render_video: bool,
    ) -> dict:
        return capture_preview_summary(
            connector=self.connector,
            settings=settings,
            output_base=output_base,
            data_dir=self.data_dir,
            emit=self.emit,
            status=self.status,
            render_snapshot=render_snapshot,
            render_video=render_video,
        )
