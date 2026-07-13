"""High-level camera API for snapshots, recordings, and RTSP streaming."""

from collections.abc import Callable
from pathlib import Path

from quii_helper.camera.connection.session import (
    CameraConnector,
    CameraPreviewSession,
)
from quii_helper.camera.device_cgi import (
    CameraDeviceAllInfo,
    CameraDeviceCapabilitiesInfo,
    CameraDeviceGeneralInfo,
    CameraDeviceNetworkInfo,
    CameraDeviceProductInfo,
    CameraDeviceScreenFlipInfo,
    CameraDeviceStorageInfo,
    CameraDeviceTimeInfo,
    CameraDeviceTimeTitleInfo,
    CameraDeviceVideoConfigInfo,
    CameraDeviceVideoSwitchInfo,
    CameraDeviceWifiListInfo,
    DeviceCgiEndpoint,
    fetch_device_all_info,
    fetch_network_info,
    fetch_product_info,
    fetch_screen_flip_info,
    fetch_storage_info,
    fetch_system_capabilities,
    fetch_system_general_info,
    fetch_time_info,
    fetch_time_title_info,
    fetch_video_config_info,
    fetch_video_switch_info,
    fetch_wifi_list_info,
    resolve_device_cgi_endpoint,
)
from quii_helper.camera.metadata import (
    CameraDeviceInfo,
    camera_device_info_from_credentials,
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
from quii_helper.cloud.devices import (
    fetch_cloud_device_list,
    find_cloud_device,
)
from quii_helper.config import AutonomousConfig, RuntimeCredentials
from quii_helper.io.paths import DATA_DIR
from quii_helper.models.capture import CaptureSummary
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
    "CameraDeviceAllInfo",
    "CameraDeviceCapabilitiesInfo",
    "CameraDeviceGeneralInfo",
    "CameraDeviceInfo",
    "CameraDeviceNetworkInfo",
    "CameraPreviewSession",
    "CameraDeviceProductInfo",
    "CameraDeviceScreenFlipInfo",
    "CameraDeviceStorageInfo",
    "CameraDeviceTimeInfo",
    "CameraDeviceTimeTitleInfo",
    "CameraDeviceVideoConfigInfo",
    "CameraDeviceVideoSwitchInfo",
    "CameraDeviceWifiListInfo",
]


def _default_emit(obj: object) -> None:
    logger.debug("{}", obj)


def _default_status(message: str) -> None:
    logger.info(message)


class Camera:
    """User-facing camera client.

    `Camera` is the stable entrypoint for application code. It resolves
    runtime credentials, opens the device preview session, receives media
    packets, and exposes high-level operations for snapshots, recordings, and
    RTSP streaming.

    Configuration:
        Values can be supplied through an `AutonomousConfig` instance, through
        keyword overrides, or through environment-backed defaults loaded by the
        config layer. Keyword arguments override the passed config object for
        this `Camera` instance only.
    """

    def __init__(
        self,
        config: AutonomousConfig | None = None,
        *,
        device_id: str | None = None,
        cloud_username: str | None = None,
        cloud_account: str | None = None,
        cloud_password: str | None = None,
        device_host: str | None = None,
        auth_code: str | None = None,
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
        tls_verify: bool | None = None,
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
            device_host: Camera LAN IP address or hostname used by local
                `/tdkcgi` read-only HTTP methods.
            auth_code: Device auth code used by local `/tdkcgi` read-only HTTP
                methods.
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
            tls_verify: Whether HTTPS certificate verification is enabled for
                cloud/device requests.
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
        self._runtime_credentials: RuntimeCredentials | None = None

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
                For a snapshot this should end in `.jpg`; for a video this
                should end in `.mp4`. When omitted, files are written under
                `data_dir` with a timestamped name.
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

    def get_device_info(self) -> CameraDeviceInfo:
        """Fetch read-only cloud metadata for this camera.

        This method performs cloud login, `get-device-token`, and a best-effort
        `get-device-list` lookup, but it does not open a live preview session
        and does not contact the camera media transport. Sensitive runtime
        credentials are intentionally omitted from the returned object.

        Returns:
            `CameraDeviceInfo` with device id, channel count, model/type, share
            flags, and transparent vendor metadata when the cloud provides it.
        """

        credentials = self._fetch_runtime_credentials()
        cloud_device = None
        try:
            cloud_device = find_cloud_device(
                fetch_cloud_device_list(
                    self.config,
                    session_id=credentials.session_id,
                ),
                self.config.device_id,
            )
        except Exception as exc:
            logger.debug("device-list lookup failed: {}", exc)
        return camera_device_info_from_credentials(
            self.config,
            credentials,
            cloud_device=cloud_device,
        )

    def _fetch_runtime_credentials(self) -> RuntimeCredentials:
        if self._runtime_credentials is None:
            self._runtime_credentials = self.connector.fetch_credentials()
        return self._runtime_credentials

    def _resolve_local_cgi_endpoint(
        self,
        *,
        port: int,
        scheme: str,
        auth_code: str | None,
        verify_tls: bool | None,
        debug: bool,
    ) -> DeviceCgiEndpoint:
        resolved_auth_code = auth_code
        return resolve_device_cgi_endpoint(
            self.config,
            port=port,
            scheme=scheme,
            auth_code=resolved_auth_code,
            verify_tls=verify_tls,
            debug=debug,
        )

    def get_device_all_info(
        self,
        *,
        port: int = 80,
        scheme: str = "http",
        auth_code: str | None = None,
        verify_tls: bool | None = None,
        debug: bool = False,
    ) -> CameraDeviceAllInfo:
        """Fetch broad read-only device status from `/tdkcgi`.

        This mirrors the original app's `get.device.status` request. It is a
        direct HTTP CGI call to `Camera(..., device_host=...)`, not a cloud or
        live-preview call.

        Args:
            port: Camera CGI HTTP(S) port. The original app defaults to `80`
                for HTTP and `443` for HTTPS-capable devices.
            scheme: URL scheme, usually `"http"` for LAN CGI access.
            auth_code: Optional explicit device auth code. When omitted,
                `Camera(..., auth_code=...)` or `AUTH_CODE` from `.env` is
                used. This method never performs cloud login by itself.
            verify_tls: Override TLS certificate verification for HTTPS CGI.
            debug: Enable debug logging for the raw CGI exchange.

        Returns:
            `CameraDeviceAllInfo` with stable fields and raw parsed content.
        """

        return fetch_device_all_info(
            self._resolve_local_cgi_endpoint(
                port=port,
                scheme=scheme,
                auth_code=auth_code,
                verify_tls=verify_tls,
                debug=debug,
            )
        )

    def get_product_info(
        self,
        *,
        port: int = 80,
        scheme: str = "http",
        auth_code: str | None = None,
        verify_tls: bool | None = None,
        debug: bool = False,
    ) -> CameraDeviceProductInfo:
        """Fetch read-only product identity from `/tdkcgi`.

        This mirrors the original app's `get.product.info` request and uses
        `Camera(..., device_host=...)`.

        Args:
            port: Camera CGI HTTP(S) port.
            scheme: URL scheme, usually `"http"` for LAN CGI access.
            auth_code: Optional explicit device auth code. When omitted,
                `Camera(..., auth_code=...)` or `AUTH_CODE` from `.env` is
                used. This method never performs cloud login by itself.
            verify_tls: Override TLS certificate verification for HTTPS CGI.
            debug: Enable debug logging for the raw CGI exchange.

        Returns:
            `CameraDeviceProductInfo` with MAC, firmware version, release date,
            and model.
        """

        return fetch_product_info(
            self._resolve_local_cgi_endpoint(
                port=port,
                scheme=scheme,
                auth_code=auth_code,
                verify_tls=verify_tls,
                debug=debug,
            )
        )

    def get_storage_info(
        self,
        *,
        port: int = 80,
        scheme: str = "http",
        auth_code: str | None = None,
        verify_tls: bool | None = None,
        debug: bool = False,
    ) -> CameraDeviceStorageInfo:
        """Fetch read-only storage status from `/tdkcgi`.

        This mirrors the original app's `get.hdd.base` request and uses
        `Camera(..., device_host=...)`.

        Args:
            port: Camera CGI HTTP(S) port.
            scheme: URL scheme, usually `"http"` for LAN CGI access.
            auth_code: Optional explicit device auth code. When omitted,
                `Camera(..., auth_code=...)` or `AUTH_CODE` from `.env` is
                used. This method never performs cloud login by itself.
            verify_tls: Override TLS certificate verification for HTTPS CGI.
            debug: Enable debug logging for the raw CGI exchange.

        Returns:
            `CameraDeviceStorageInfo` with aggregate and per-disk fields.
        """

        return fetch_storage_info(
            self._resolve_local_cgi_endpoint(
                port=port,
                scheme=scheme,
                auth_code=auth_code,
                verify_tls=verify_tls,
                debug=debug,
            )
        )

    def get_time_info(
        self,
        *,
        port: int = 80,
        scheme: str = "http",
        auth_code: str | None = None,
        verify_tls: bool | None = None,
        debug: bool = False,
    ) -> CameraDeviceTimeInfo:
        """Fetch read-only device time/timezone from `/tdkcgi`.

        This mirrors the original app's `get.product.time` request and uses
        `Camera(..., device_host=...)`.

        Args:
            port: Camera CGI HTTP(S) port.
            scheme: URL scheme, usually `"http"` for LAN CGI access.
            auth_code: Optional explicit device auth code. When omitted,
                `Camera(..., auth_code=...)` or `AUTH_CODE` from `.env` is
                used. This method never performs cloud login by itself.
            verify_tls: Override TLS certificate verification for HTTPS CGI.
            debug: Enable debug logging for the raw CGI exchange.

        Returns:
            `CameraDeviceTimeInfo` with timezone and device datetime.
        """

        return fetch_time_info(
            self._resolve_local_cgi_endpoint(
                port=port,
                scheme=scheme,
                auth_code=auth_code,
                verify_tls=verify_tls,
                debug=debug,
            )
        )

    def get_wifi_list(
        self,
        *,
        port: int = 80,
        scheme: str = "http",
        auth_code: str | None = None,
        verify_tls: bool | None = None,
        debug: bool = False,
    ) -> CameraDeviceWifiListInfo:
        """Fetch read-only Wi-Fi scan results from `/tdkcgi`.

        This mirrors the original app's `get.wifi.list` request and uses
        `Camera(..., device_host=...)`.

        Args:
            port: Camera CGI HTTP(S) port.
            scheme: URL scheme, usually `"http"` for LAN CGI access.
            auth_code: Optional explicit device auth code. When omitted,
                `Camera(..., auth_code=...)` or `AUTH_CODE` from `.env` is
                used. This method never performs cloud login by itself.
            verify_tls: Override TLS certificate verification for HTTPS CGI.
            debug: Enable debug logging for the raw CGI exchange.

        Returns:
            `CameraDeviceWifiListInfo` with visible Wi-Fi networks.
        """

        return fetch_wifi_list_info(
            self._resolve_local_cgi_endpoint(
                port=port,
                scheme=scheme,
                auth_code=auth_code,
                verify_tls=verify_tls,
                debug=debug,
            )
        )

    def get_screen_flip_info(
        self,
        *,
        port: int = 80,
        scheme: str = "http",
        auth_code: str | None = None,
        verify_tls: bool | None = None,
        debug: bool = False,
    ) -> CameraDeviceScreenFlipInfo:
        """Fetch read-only screen flip/rotation state from `/tdkcgi`.

        This mirrors the original app's `get.shape.mirror` request and uses
        `Camera(..., device_host=...)`.

        Args:
            port: Camera CGI HTTP(S) port.
            scheme: URL scheme, usually `"http"` for LAN CGI access.
            auth_code: Optional explicit device auth code. When omitted,
                `Camera(..., auth_code=...)` or `AUTH_CODE` from `.env` is
                used. This method never performs cloud login by itself.
            verify_tls: Override TLS certificate verification for HTTPS CGI.
            debug: Enable debug logging for the raw CGI exchange.

        Returns:
            `CameraDeviceScreenFlipInfo` with native `state`, `angle`, and raw
            string values.
        """

        return fetch_screen_flip_info(
            self._resolve_local_cgi_endpoint(
                port=port,
                scheme=scheme,
                auth_code=auth_code,
                verify_tls=verify_tls,
                debug=debug,
            )
        )

    def get_video_switch_info(
        self,
        *,
        port: int = 80,
        scheme: str = "http",
        auth_code: str | None = None,
        verify_tls: bool | None = None,
        debug: bool = False,
    ) -> CameraDeviceVideoSwitchInfo:
        """Fetch read-only video on/off state from `/tdkcgi`.

        This mirrors the original app's `get.videoswitch.vionoff` request and
        uses `Camera(..., device_host=...)`.

        Args:
            port: Camera CGI HTTP(S) port.
            scheme: URL scheme, usually `"http"` for LAN CGI access.
            auth_code: Optional explicit device auth code. When omitted,
                `Camera(..., auth_code=...)` or `AUTH_CODE` from `.env` is
                used. This method never performs cloud login by itself.
            verify_tls: Override TLS certificate verification for HTTPS CGI.
            debug: Enable debug logging for the raw CGI exchange.

        Returns:
            `CameraDeviceVideoSwitchInfo` with native `state` and boolean
            `is_on`.
        """

        return fetch_video_switch_info(
            self._resolve_local_cgi_endpoint(
                port=port,
                scheme=scheme,
                auth_code=auth_code,
                verify_tls=verify_tls,
                debug=debug,
            )
        )

    def get_time_title_info(
        self,
        *,
        port: int = 80,
        scheme: str = "http",
        auth_code: str | None = None,
        verify_tls: bool | None = None,
        debug: bool = False,
    ) -> CameraDeviceTimeTitleInfo:
        """Fetch read-only time-title overlay geometry from `/tdkcgi`.

        This mirrors the original app's `get.video.timetitle` request and uses
        `Camera(..., device_host=...)`.

        Args:
            port: Camera CGI HTTP(S) port.
            scheme: URL scheme, usually `"http"` for LAN CGI access.
            auth_code: Optional explicit device auth code. When omitted,
                `Camera(..., auth_code=...)` or `AUTH_CODE` from `.env` is
                used. This method never performs cloud login by itself.
            verify_tls: Override TLS certificate verification for HTTPS CGI.
            debug: Enable debug logging for the raw CGI exchange.

        Returns:
            `CameraDeviceTimeTitleInfo` with stream/video/title geometry.
        """

        return fetch_time_title_info(
            self._resolve_local_cgi_endpoint(
                port=port,
                scheme=scheme,
                auth_code=auth_code,
                verify_tls=verify_tls,
                debug=debug,
            )
        )

    def get_network_info(
        self,
        *,
        port: int = 80,
        scheme: str = "http",
        auth_code: str | None = None,
        verify_tls: bool | None = None,
        debug: bool = False,
    ) -> CameraDeviceNetworkInfo:
        """Fetch read-only network settings from `/tdkcgi`.

        This mirrors the original app's `get.network.config` request and uses
        `Camera(..., device_host=...)`.

        Args:
            port: Camera CGI HTTP(S) port.
            scheme: URL scheme, usually `"http"` for LAN CGI access.
            auth_code: Optional explicit device auth code. When omitted,
                `Camera(..., auth_code=...)` or `AUTH_CODE` from `.env` is
                used. This method never performs cloud login by itself.
            verify_tls: Override TLS certificate verification for HTTPS CGI.
            debug: Enable debug logging for the raw CGI exchange.

        Returns:
            `CameraDeviceNetworkInfo` with top-level network fields and LAN
            interface details when the firmware provides them.
        """

        return fetch_network_info(
            self._resolve_local_cgi_endpoint(
                port=port,
                scheme=scheme,
                auth_code=auth_code,
                verify_tls=verify_tls,
                debug=debug,
            )
        )

    def get_system_general_info(
        self,
        *,
        port: int = 80,
        scheme: str = "http",
        auth_code: str | None = None,
        verify_tls: bool | None = None,
        debug: bool = False,
    ) -> CameraDeviceGeneralInfo:
        """Fetch read-only general system settings from `/tdkcgi`.

        This mirrors the original app's `get.system.general` request and uses
        `Camera(..., device_host=...)`.

        Args:
            port: Camera CGI HTTP(S) port.
            scheme: URL scheme, usually `"http"` for LAN CGI access.
            auth_code: Optional explicit device auth code. When omitted,
                `Camera(..., auth_code=...)` or `AUTH_CODE` from `.env` is
                used. This method never performs cloud login by itself.
            verify_tls: Override TLS certificate verification for HTTPS CGI.
            debug: Enable debug logging for the raw CGI exchange.

        Returns:
            `CameraDeviceGeneralInfo` with stable general settings and raw
            parsed content for firmware-specific fields.
        """

        return fetch_system_general_info(
            self._resolve_local_cgi_endpoint(
                port=port,
                scheme=scheme,
                auth_code=auth_code,
                verify_tls=verify_tls,
                debug=debug,
            )
        )

    def get_system_capabilities(
        self,
        *,
        port: int = 80,
        scheme: str = "http",
        auth_code: str | None = None,
        verify_tls: bool | None = None,
        debug: bool = False,
    ) -> CameraDeviceCapabilitiesInfo:
        """Fetch read-only system capabilities from `/tdkcgi`.

        This mirrors the original app's `get.system.ability` request and uses
        `Camera(..., device_host=...)`.

        Args:
            port: Camera CGI HTTP(S) port.
            scheme: URL scheme, usually `"http"` for LAN CGI access.
            auth_code: Optional explicit device auth code. When omitted,
                `Camera(..., auth_code=...)` or `AUTH_CODE` from `.env` is
                used. This method never performs cloud login by itself.
            verify_tls: Override TLS certificate verification for HTTPS CGI.
            debug: Enable debug logging for the raw CGI exchange.

        Returns:
            `CameraDeviceCapabilitiesInfo` with common capability flags and raw
            parsed content for firmware-specific capability blocks.
        """

        return fetch_system_capabilities(
            self._resolve_local_cgi_endpoint(
                port=port,
                scheme=scheme,
                auth_code=auth_code,
                verify_tls=verify_tls,
                debug=debug,
            )
        )

    def get_video_config(
        self,
        *,
        port: int = 80,
        scheme: str = "http",
        auth_code: str | None = None,
        verify_tls: bool | None = None,
        debug: bool = False,
    ) -> CameraDeviceVideoConfigInfo:
        """Fetch read-only video encode configuration from `/tdkcgi`.

        This mirrors the original app's full-channel `get.encode` request and
        uses `Camera(..., device_host=...)`.

        Args:
            port: Camera CGI HTTP(S) port.
            scheme: URL scheme, usually `"http"` for LAN CGI access.
            auth_code: Optional explicit device auth code. When omitted,
                `Camera(..., auth_code=...)` or `AUTH_CODE` from `.env` is
                used. This method never performs cloud login by itself.
            verify_tls: Override TLS certificate verification for HTTPS CGI.
            debug: Enable debug logging for the raw CGI exchange.

        Returns:
            `CameraDeviceVideoConfigInfo` with channel/stream encode settings.
        """

        return fetch_video_config_info(
            self._resolve_local_cgi_endpoint(
                port=port,
                scheme=scheme,
                auth_code=auth_code,
                verify_tls=verify_tls,
                debug=debug,
            )
        )

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
            with camera.serve_rtsp(port=8554) as rtsp_stream:
                # The status callback logs the URL after media is available.
                rtsp_stream.wait()
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
    ) -> CaptureSummary:
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
