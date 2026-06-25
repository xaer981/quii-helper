"""High-level camera API for snapshots, recordings, and RTSP streaming."""

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
from quii_helper.camera.streaming import CameraRtspStream
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
    """User-facing camera client.

    `Camera` is the stable entrypoint for application code. It resolves cloud
    credentials, opens the device preview session, receives media packets, and
    exposes high-level operations for snapshots, recordings, and RTSP
    streaming.

    Configuration values can be supplied either through an `AutonomousConfig`
    instance, through keyword overrides, or through the environment-backed
    defaults loaded by the config layer. Keyword arguments override the passed
    config object for this `Camera` instance only.
    """

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
        """Create a camera client.

        Args:
            config: Optional base configuration. If omitted, defaults are read
                from the config layer, including `.env` values.
            device_id: Device identifier used by the cloud and P2P services.
            cloud_username: Alias for `cloud_account`.
            cloud_account: Cloud account/login used for runtime credentials.
            cloud_password: Cloud account password.
            client_id: Client UUID sent to cloud, UST, and MQTT services.
            service_url: Cloud service-discovery URL.
            auth_url: Cloud user-auth URL.
            oem: Camera application OEM code from the original app.
            app_id: Camera application id from the original app.
            client_type: Camera application client type from the original app.
            ca_path: TLS CA certificate path for cloud service discovery.
            cert_path: TLS client certificate path for cloud service discovery.
            key_path: TLS client private key path for cloud service discovery.
            ip_region_id: Cloud login IP region id.
            live_play_payload: QUII live-play payload mode, usually `"path"`.
            live_inner: Whether to use the inner live-play packet variant.
            live_newcn: Whether to use the new connection flag in live-play.
            live_keepalive_interval: Seconds between live keepalive packets.
            play_sync_iterations: Number of extra post-play sync iterations.
            enable_play_probes: Whether to send additional play probe packets.
            channel: Camera channel number.
            stream: Numeric stream selector accepted by the device.
            stream_quality: Friendly stream selector, for example `"high"` or
                `"low"`. Mutually exclusive with `stream`.
            preview_settings: Low-level capture settings. Most users should
                keep the default.
            data_dir: Directory for generated media and optional diagnostics.
            emit: Callback for structured debug summaries.
            status: Callback for user-facing status messages.

        Raises:
            ValueError: If mutually exclusive stream selectors are supplied or
                an invalid non-negative option is provided.
        """
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
        """Capture media from the camera and return a structured result.

        This is the common implementation behind `snapshot()`, `save_video()`,
        and `record()`. It can render a snapshot, an MP4 file, or both,
        depending on the render flags.

        Args:
            duration_seconds: Capture window in seconds. If omitted, the value
                from `preview_settings.capture_seconds` is used.
            output_path: Optional target path.
            For a snapshot this should end in `.jpg`;
                for a video this should end in `.mp4`.
            When omitted,
                files are written under `data_dir` with a timestamped name.
            save_diagnostic_artifacts: Overrides diagnostic artifact saving for
                this capture only.
            stop_when_decodable: Overrides whether capture may stop as soon as
                enough H.264 context is available.
            render_snapshot: Whether to render a JPEG snapshot.
            render_video: Whether to render an MP4 video.

        Returns:
            `CameraCaptureResult` with generated paths, write flags,
            and the raw capture summary for diagnostics.

        Raises:
            ValueError: If `output_path` has an incompatible suffix.
            CameraCaptureError: Not raised directly by this method, but can be
                raised by `CameraCaptureResult.require_snapshot()` or
                `CameraCaptureResult.require_video()`.
        """
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
        """Capture one JPEG snapshot.

        Args:
            timeout_seconds: Maximum time to wait for a decodable frame.
            output_path: Optional `.jpg` output path. When omitted, a
                timestamped file is created under `data_dir`.

        Returns:
            Path to the written JPEG file.

        Raises:
            CameraCaptureError: If no snapshot could be produced.
            ValueError: If `output_path` does not end in `.jpg`.
        """
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
        """Record an MP4 video for the requested capture window.

        Args:
            duration_seconds: Desired capture duration in seconds.
            output_path: Optional `.mp4` output path. When omitted, a
                timestamped file is created under `data_dir`.

        Returns:
            Path to the written MP4 file.

        Raises:
            CameraCaptureError: If no video could be produced.
            ValueError: If `output_path` does not end in `.mp4`.
        """
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
        """Alias for `save_video()`.

        Args:
            duration_seconds: Desired capture duration in seconds.
            output_path: Optional `.mp4` output path.

        Returns:
            Path to the written MP4 file.
        """
        return self.save_video(duration_seconds, output_path=output_path)

    def serve_rtsp(
        self,
        *,
        host: str = "0.0.0.0",
        port: int = 8554,
        path: str = "/live",
    ) -> CameraRtspStream:
        """Start an RTSP server backed by live camera packets.

        The returned handle owns both the RTSP server and the background camera
        packet producer. Call `close()` when the stream is no longer needed, or
        use the returned object as a context manager.

        Example:
            ```python
            with camera.serve_rtsp(port=8554) as stream:
                print(stream.url)
                stream.wait()
            ```

        Args:
            host: Interface to bind. Use `"0.0.0.0"` to listen on all
                interfaces.
            port: TCP port for the RTSP server.
            path: RTSP path, for example `"/live"`.

        Returns:
            Started `CameraRtspStream` handle. The client URL is available as
            `handle.url`.
        """
        stream = CameraRtspStream(
            connector=self.connector,
            preview_settings=self.preview_settings,
            data_dir=self.data_dir,
            emit=self.emit,
            status=self.status,
            host=host,
            port=port,
            path=path,
        )
        return stream.start()

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
