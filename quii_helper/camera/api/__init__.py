"""High-level camera API for snapshots, recordings, and RTSP streaming."""

from collections.abc import Callable, Sequence
from pathlib import Path

from quii_helper.camera.connection.session import (
    CameraConnector,
    CameraPreviewSession,
)
from quii_helper.camera.device_cgi import (
    CameraDeviceAlarmChannel,
    CameraDeviceAlarmChannelInfo,
    CameraDeviceAlarmInputChannel,
    CameraDeviceAlarmInputInfo,
    CameraDeviceAlarmMotionDetectionInfo,
    CameraDeviceAlarmScheduleDay,
    CameraDeviceAlarmScheduleInfo,
    CameraDeviceAlarmScheduleSlot,
    CameraDeviceAlarmVideoLostInfo,
    CameraDeviceAlarmVideoShelterInfo,
    CameraDeviceAllInfo,
    CameraDeviceAttachmentAlarm,
    CameraDeviceAttachmentChannel,
    CameraDeviceAttachmentElevator,
    CameraDeviceAttachmentInfo,
    CameraDeviceAttachmentLock,
    CameraDeviceAttachmentProfile,
    CameraDeviceAttachmentSmartSwitch,
    CameraDeviceCapabilitiesInfo,
    CameraDeviceCommandStatus,
    CameraDeviceFpsChannelInfo,
    CameraDeviceFpsInfo,
    CameraDeviceGeneralInfo,
    CameraDeviceHumanTraceInfo,
    CameraDeviceLanInfo,
    CameraDeviceMotionDetectionInfo,
    CameraDeviceMoveDetectionInfo,
    CameraDeviceNetworkBaseAbility,
    CameraDeviceNetworkBaseInfo,
    CameraDeviceNetworkInfo,
    CameraDeviceNetworkTransferPolicy,
    CameraDeviceProductInfo,
    CameraDeviceProfile,
    CameraDevicePtzPreset,
    CameraDevicePtzPresetInfo,
    CameraDevicePtzStateInfo,
    CameraDeviceQrCodeInfo,
    CameraDeviceRecordAlarmInfo,
    CameraDeviceRecordConfigInfo,
    CameraDeviceRecordFileInfo,
    CameraDeviceRecordListInfo,
    CameraDeviceRecordMessageInfo,
    CameraDeviceRecordScheduleTime,
    CameraDeviceRecordSessionInfo,
    CameraDeviceScreenFlipInfo,
    CameraDeviceSmartLightInfo,
    CameraDeviceSmartLightItem,
    CameraDeviceSoundLightChannelInfo,
    CameraDeviceSoundLightInfo,
    CameraDeviceStorageInfo,
    CameraDeviceStreamKeyInfo,
    CameraDeviceStreamProfile,
    CameraDeviceTfCardDiskInfo,
    CameraDeviceTfCardInfo,
    CameraDeviceTimeInfo,
    CameraDeviceTimeTitleInfo,
    CameraDeviceUpgradeProcessInfo,
    CameraDeviceUpgradeStatusInfo,
    CameraDeviceUpgradeVersionInfo,
    CameraDeviceVideoChannelInfo,
    CameraDeviceVideoConfigInfo,
    CameraDeviceVideoSwitchInfo,
    CameraDeviceWifiListInfo,
    DeviceCgiEndpoint,
    fetch_alarm_channel_info,
    fetch_alarm_input_info,
    fetch_alarm_input_schedule_info,
    fetch_alarm_motion_detection_info,
    fetch_alarm_motion_detection_schedule_info,
    fetch_alarm_video_lost_info,
    fetch_alarm_video_lost_schedule_info,
    fetch_alarm_video_shelter_info,
    fetch_alarm_video_shelter_schedule_info,
    fetch_device_all_info,
    fetch_device_attachment_info,
    fetch_device_profile,
    fetch_fps_info,
    fetch_human_trace_info,
    fetch_motion_detection_info,
    fetch_move_detection_info,
    fetch_network_base_info,
    fetch_network_info,
    fetch_product_info,
    fetch_ptz_preset_info,
    fetch_ptz_state_info,
    fetch_qr_code_info,
    fetch_record_alarm_info,
    fetch_record_config_info,
    fetch_record_list_info,
    fetch_record_message_info,
    fetch_record_session_info,
    fetch_screen_flip_info,
    fetch_smart_light_info,
    fetch_sound_light_info,
    fetch_storage_info,
    fetch_stream_key_info,
    fetch_system_capabilities,
    fetch_system_general_info,
    fetch_tf_card_info,
    fetch_time_info,
    fetch_time_title_info,
    fetch_upgrade_process_info,
    fetch_upgrade_status_info,
    fetch_upgrade_version_info,
    fetch_video_config_info,
    fetch_video_switch_info,
    fetch_wifi_list_info,
    network_interfaces_from_network_info,
    resolve_device_cgi_endpoint,
    stream_profiles_from_video_config,
)
from quii_helper.camera.device_json_cgi import (
    CameraDeviceAlarmDetailChannelInfo,
    CameraDeviceAlarmDetailInfo,
    CameraDeviceAlarmDetailIntervalInfo,
    CameraDeviceAlarmDetailLevelInfo,
    CameraDeviceAlarmDetailRegionInfo,
    CameraDeviceAlarmDetailSmartFilterInfo,
    CameraDeviceAlarmStatusInfo,
    CameraDeviceAudioSessionInfo,
    CameraDeviceAudioVolumeInfo,
    CameraDeviceAudioVolumeRange,
    CameraDeviceBabysitterStateInfo,
    CameraDeviceCityCoordinateInfo,
    CameraDeviceFloodlightInfo,
    CameraDeviceFloodlightScheduleDayInfo,
    CameraDeviceFloodlightScheduleInfo,
    CameraDeviceFloodlightSchedulePlanInfo,
    CameraDeviceFloodlightScheduleTimeInfo,
    CameraDeviceFloodlightSwitchInfo,
    CameraDeviceHardwareInfo,
    CameraDeviceJsonFpsModeInfo,
    CameraDeviceLightInfo,
    CameraDeviceLightItemInfo,
    CameraDeviceLightRoomInfo,
    CameraDeviceLockInfo,
    CameraDeviceLockStatusInfo,
    CameraDeviceLockTimeInfo,
    CameraDevicePirConfigInfo,
    CameraDevicePirScheduleDayInfo,
    CameraDevicePirScheduleSlotInfo,
    CameraDeviceSmartSwitchChannelInfo,
    CameraDeviceSmartSwitchInfo,
    CameraDeviceSmartSwitchItemInfo,
    CameraDeviceSmartSwitchRoomInfo,
    CameraDeviceThirdPartyPushInfo,
    CameraDeviceThirdPartyPushScheduleDayInfo,
    CameraDeviceThirdPartyPushScheduleSlotInfo,
    CameraDeviceVoiceFileInfo,
    CameraDeviceVoiceMessageInfo,
    fetch_alarm_detail_info,
    fetch_alarm_status_info,
    fetch_audio_session_info,
    fetch_audio_volume_info,
    fetch_babysitter_state_info,
    fetch_city_coordinate_info,
    fetch_floodlight_schedule_info,
    fetch_floodlight_switch_info,
    fetch_hardware_info,
    fetch_json_fps_mode_info,
    fetch_light_info,
    fetch_lock_status_info,
    fetch_pir_config_info,
    fetch_smart_switch_info,
    fetch_third_party_push_info,
    fetch_voice_message_info,
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
from quii_helper.cloud.iot import (
    CameraIotCommandSupportInfo,
    fetch_iot_command_support,
)
from quii_helper.cloud.shadow import (
    CameraDeviceShadowInfo,
    CameraDeviceShadowState,
    CameraDeviceShadowSwitchState,
    fetch_device_shadow_info,
)
from quii_helper.config import AutonomousConfig, RuntimeCredentials
from quii_helper.io.paths import DATA_DIR
from quii_helper.models.capture import CaptureSummary
from quii_helper.network import (
    LanDeviceCandidate,
    discover_local_ips,
)
from quii_helper.network import (
    discover_lan_devices as discover_network_lan_devices,
)
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
    "CameraDeviceAlarmChannel",
    "CameraDeviceAlarmChannelInfo",
    "CameraDeviceAlarmInputChannel",
    "CameraDeviceAlarmInputInfo",
    "CameraDeviceAlarmMotionDetectionInfo",
    "CameraDeviceAlarmScheduleDay",
    "CameraDeviceAlarmScheduleInfo",
    "CameraDeviceAlarmScheduleSlot",
    "CameraDeviceAlarmVideoLostInfo",
    "CameraDeviceAlarmVideoShelterInfo",
    "CameraDeviceAlarmDetailChannelInfo",
    "CameraDeviceAlarmDetailInfo",
    "CameraDeviceAlarmDetailIntervalInfo",
    "CameraDeviceAlarmDetailLevelInfo",
    "CameraDeviceAlarmDetailRegionInfo",
    "CameraDeviceAlarmDetailSmartFilterInfo",
    "CameraDeviceAlarmStatusInfo",
    "CameraDeviceAttachmentAlarm",
    "CameraDeviceAttachmentChannel",
    "CameraDeviceAttachmentElevator",
    "CameraDeviceAttachmentInfo",
    "CameraDeviceAttachmentLock",
    "CameraDeviceAttachmentProfile",
    "CameraDeviceAttachmentSmartSwitch",
    "CameraDeviceCapabilitiesInfo",
    "CameraDeviceCommandStatus",
    "CameraDeviceAudioSessionInfo",
    "CameraDeviceAudioVolumeInfo",
    "CameraDeviceAudioVolumeRange",
    "CameraDeviceBabysitterStateInfo",
    "CameraDeviceCityCoordinateInfo",
    "CameraDeviceFloodlightInfo",
    "CameraDeviceFloodlightScheduleDayInfo",
    "CameraDeviceFloodlightScheduleInfo",
    "CameraDeviceFloodlightSchedulePlanInfo",
    "CameraDeviceFloodlightScheduleTimeInfo",
    "CameraDeviceFloodlightSwitchInfo",
    "CameraDeviceFpsChannelInfo",
    "CameraDeviceFpsInfo",
    "CameraDeviceGeneralInfo",
    "CameraDeviceHardwareInfo",
    "CameraDeviceHumanTraceInfo",
    "CameraDeviceInfo",
    "CameraIotCommandSupportInfo",
    "CameraDeviceLanInfo",
    "CameraDeviceLightInfo",
    "CameraDeviceLightItemInfo",
    "CameraDeviceLightRoomInfo",
    "CameraDeviceMoveDetectionInfo",
    "CameraDeviceMotionDetectionInfo",
    "CameraDeviceNetworkBaseAbility",
    "CameraDeviceNetworkBaseInfo",
    "CameraDeviceNetworkInfo",
    "CameraDeviceNetworkTransferPolicy",
    "CameraDeviceJsonFpsModeInfo",
    "CameraDeviceLockInfo",
    "CameraDeviceLockStatusInfo",
    "CameraDeviceLockTimeInfo",
    "CameraDevicePirConfigInfo",
    "CameraDevicePirScheduleDayInfo",
    "CameraDevicePirScheduleSlotInfo",
    "CameraPreviewSession",
    "CameraDeviceProductInfo",
    "CameraDeviceQrCodeInfo",
    "CameraDeviceRecordAlarmInfo",
    "CameraDeviceRecordConfigInfo",
    "CameraDeviceRecordFileInfo",
    "CameraDeviceRecordListInfo",
    "CameraDeviceRecordMessageInfo",
    "CameraDeviceRecordScheduleTime",
    "CameraDeviceRecordSessionInfo",
    "CameraDevicePtzPreset",
    "CameraDevicePtzPresetInfo",
    "CameraDevicePtzStateInfo",
    "CameraDeviceProfile",
    "CameraDeviceScreenFlipInfo",
    "CameraDeviceShadowInfo",
    "CameraDeviceShadowState",
    "CameraDeviceShadowSwitchState",
    "CameraDeviceSmartLightInfo",
    "CameraDeviceSmartLightItem",
    "CameraDeviceSmartSwitchChannelInfo",
    "CameraDeviceSmartSwitchInfo",
    "CameraDeviceSmartSwitchItemInfo",
    "CameraDeviceSmartSwitchRoomInfo",
    "CameraDeviceThirdPartyPushInfo",
    "CameraDeviceThirdPartyPushScheduleDayInfo",
    "CameraDeviceThirdPartyPushScheduleSlotInfo",
    "CameraDeviceSoundLightChannelInfo",
    "CameraDeviceSoundLightInfo",
    "CameraDeviceStorageInfo",
    "CameraDeviceStreamKeyInfo",
    "CameraDeviceTfCardDiskInfo",
    "CameraDeviceTfCardInfo",
    "CameraDeviceStreamProfile",
    "CameraDeviceTimeInfo",
    "CameraDeviceTimeTitleInfo",
    "CameraDeviceUpgradeProcessInfo",
    "CameraDeviceUpgradeStatusInfo",
    "CameraDeviceUpgradeVersionInfo",
    "CameraDeviceVideoChannelInfo",
    "CameraDeviceVideoConfigInfo",
    "CameraDeviceVideoSwitchInfo",
    "CameraDeviceVoiceFileInfo",
    "CameraDeviceVoiceMessageInfo",
    "CameraDeviceWifiListInfo",
    "LanDeviceCandidate",
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

    def get_device_shadow_info(self) -> CameraDeviceShadowInfo:
        """Fetch read-only cloud shadow status for this camera.

        This mirrors the original app's `getDeviceShadowInfo()` path:
        cloud access token + OpenAPI/IoT service discovery + `POST
        /openapi-tdk/device/status` with the `Device_state` field. It does not
        open a live preview session.

        Returns:
            `CameraDeviceShadowInfo` with the parsed `Device_state` block and
            raw cloud JSON for vendor-specific fields.
        """

        return fetch_device_shadow_info(
            self.config,
            credentials=self._fetch_runtime_credentials(),
        )

    def get_iot_command_support(self) -> CameraIotCommandSupportInfo:
        """Fetch read-only IoT/RRPC command support for this camera.

        This mirrors the original app's `QvIotControlManager` support probe:
        cloud access token + IoT service discovery + HTTP `synccontrol` with
        the `get.rrpc.commandlist` command. It does not send any set/unlock
        command and does not open a live preview session.

        Returns:
            `CameraIotCommandSupportInfo` with the raw native command list and
            normalized support flags for known IoT/RRPC commands.
        """

        return fetch_iot_command_support(
            self.config,
            credentials=self._fetch_runtime_credentials(),
        )

    def discover_lan_devices(
        self,
        *,
        local_ips: Sequence[str] | None = None,
        hosts: Sequence[str] | None = None,
        subnet_prefix: int = 24,
        http_port: int = 80,
        stream_port: int = 34567,
        timeout: float = 0.3,
        max_workers: int = 64,
        require_qualvision: bool = True,
    ) -> list[LanDeviceCandidate]:
        """Discover Qualvision-compatible devices on the local network.

        Discovery is read-only: it checks the HTTP `Server` header from
        `GET /` and whether the native TCP stream port is open. It does not
        send credentials and does not call `/tdkcgi`.

        Args:
            local_ips: Local IPv4 addresses used to derive `/24` scan ranges.
                When omitted and `hosts` is not provided, local addresses are
                detected automatically.
            hosts: Explicit hosts to probe. When provided, subnet derivation is
                skipped.
            subnet_prefix: Prefix length used for host derivation from
                `local_ips`.
            http_port: HTTP port to probe for the `Server` header.
            stream_port: Native TCP stream/control port to probe.
            timeout: Per-probe timeout in seconds.
            max_workers: Maximum number of concurrent host probes.
            require_qualvision: Keep only candidates with a Qualvision-looking
                HTTP `Server` header.

        Returns:
            List of LAN device candidates suitable for `Camera(device_host=...)`.
        """

        resolved_local_ips = (
            list(local_ips)
            if local_ips is not None
            else ([] if hosts is not None else discover_local_ips())
        )
        return discover_network_lan_devices(
            local_ips=resolved_local_ips,
            hosts=hosts,
            subnet_prefix=subnet_prefix,
            http_port=http_port,
            stream_port=stream_port,
            timeout=timeout,
            max_workers=max_workers,
            require_qualvision=require_qualvision,
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

    def get_alarm_channel_info(
        self,
        *,
        port: int = 80,
        scheme: str = "http",
        auth_code: str | None = None,
        verify_tls: bool | None = None,
        debug: bool = False,
    ) -> CameraDeviceAlarmChannelInfo:
        """Fetch read-only alarm channel names from `/tdkcgi`.

        This mirrors the original app's `get.encode.channelname` request and
        returns the channel id, display name, type, and serial number used by
        alarm-related configuration calls.

        Args:
            port: Camera CGI HTTP(S) port.
            scheme: URL scheme, usually `"http"` for LAN CGI access.
            auth_code: Optional explicit device auth code. When omitted,
                `Camera(..., auth_code=...)` or `AUTH_CODE` from `.env` is
                used. This method never performs cloud login by itself.
            verify_tls: Override TLS certificate verification for HTTPS CGI.
            debug: Enable debug logging for the raw CGI exchange.

        Returns:
            `CameraDeviceAlarmChannelInfo` with alarm channel entries.
        """

        return fetch_alarm_channel_info(
            self._resolve_local_cgi_endpoint(
                port=port,
                scheme=scheme,
                auth_code=auth_code,
                verify_tls=verify_tls,
                debug=debug,
            )
        )

    def get_alarm_input_info(
        self,
        *,
        channel_id: int = -1,
        port: int = 80,
        scheme: str = "http",
        auth_code: str | None = None,
        verify_tls: bool | None = None,
        debug: bool = False,
    ) -> CameraDeviceAlarmInputInfo:
        """Fetch read-only alarm input channel state from `/tdkcgi`.

        This mirrors the original app's `get.alarm.alarmin` request. Native
        code sends a simple request for all inputs when `channel_id == -1`,
        otherwise it sends `<channel>{channel_id}</channel>`.

        Args:
            channel_id: Native alarm input channel number, or `-1` for all
                channels.
            port: Camera CGI HTTP(S) port.
            scheme: URL scheme, usually `"http"` for LAN CGI access.
            auth_code: Optional explicit device auth code. When omitted,
                `Camera(..., auth_code=...)` or `AUTH_CODE` from `.env` is
                used. This method never performs cloud login by itself.
            verify_tls: Override TLS certificate verification for HTTPS CGI.
            debug: Enable debug logging for the raw CGI exchange.

        Returns:
            `CameraDeviceAlarmInputInfo` with alarm input channel entries.
        """

        return fetch_alarm_input_info(
            self._resolve_local_cgi_endpoint(
                port=port,
                scheme=scheme,
                auth_code=auth_code,
                verify_tls=verify_tls,
                debug=debug,
            ),
            channel_id=channel_id,
        )

    def get_alarm_detail_info(
        self,
        *,
        alarm_type: int,
        port: int = 80,
        scheme: str = "http",
        auth_code: str | None = None,
        verify_tls: bool | None = None,
        debug: bool = False,
    ) -> CameraDeviceAlarmDetailInfo:
        """Fetch read-only alarm detail config from JSON `/tdkcgi`.

        This mirrors the original app's `get.alarm.detailInfo` JSON request,
        where native code sends `body.content.alarmtype` as the selector for
        the alarm detail block to return.

        Args:
            alarm_type: Native alarm detail type sent as JSON
                `content.alarmtype`.
            port: Camera CGI HTTP(S) port.
            scheme: URL scheme, usually `"http"` for LAN CGI access.
            auth_code: Optional explicit device auth code. When omitted,
                `Camera(..., auth_code=...)` or `AUTH_CODE` from `.env` is
                used. This method never performs cloud login by itself.
            verify_tls: Override TLS certificate verification for HTTPS CGI.
            debug: Enable debug logging for the raw CGI exchange.

        Returns:
            `CameraDeviceAlarmDetailInfo` with the selected alarm detail
            channel config.
        """

        return fetch_alarm_detail_info(
            self._resolve_local_cgi_endpoint(
                port=port,
                scheme=scheme,
                auth_code=auth_code,
                verify_tls=verify_tls,
                debug=debug,
            ),
            alarm_type=alarm_type,
        )

    def get_alarm_status_info(
        self,
        *,
        port: int = 80,
        scheme: str = "http",
        auth_code: str | None = None,
        verify_tls: bool | None = None,
        debug: bool = False,
    ) -> CameraDeviceAlarmStatusInfo:
        """Fetch read-only alarm status from custom JSON `/tdkcgi`.

        This mirrors the original app's `get.alarm.status` custom JSON
        request. Native code maps `status == "on"` to a boolean; this method
        keeps the raw status string and exposes `is_on` as a convenience.

        Args:
            port: Camera CGI HTTP(S) port.
            scheme: URL scheme, usually `"http"` for LAN CGI access.
            auth_code: Optional explicit device auth code. When omitted,
                `Camera(..., auth_code=...)` or `AUTH_CODE` from `.env` is
                used. This method never performs cloud login by itself.
            verify_tls: Override TLS certificate verification for HTTPS CGI.
            debug: Enable debug logging for the raw CGI exchange.

        Returns:
            `CameraDeviceAlarmStatusInfo` with raw status and boolean mapping.
        """

        return fetch_alarm_status_info(
            self._resolve_local_cgi_endpoint(
                port=port,
                scheme=scheme,
                auth_code=auth_code,
                verify_tls=verify_tls,
                debug=debug,
            )
        )

    def get_device_attachment_info(
        self,
        *,
        port: int = 80,
        scheme: str = "http",
        auth_code: str | None = None,
        verify_tls: bool | None = None,
        debug: bool = False,
    ) -> CameraDeviceAttachmentInfo:
        """Fetch read-only sub-device attachment info from `/tdkcgi`.

        This mirrors the original app's `get.device.attachInfo` request. It
        exposes channel attachment metadata, locks, elevators, alarm state, and
        smart switch summary when firmware provides those blocks.

        Args:
            port: Camera CGI HTTP(S) port.
            scheme: URL scheme, usually `"http"` for LAN CGI access.
            auth_code: Optional explicit device auth code. When omitted,
                `Camera(..., auth_code=...)` or `AUTH_CODE` from `.env` is
                used. This method never performs cloud login by itself.
            verify_tls: Override TLS certificate verification for HTTPS CGI.
            debug: Enable debug logging for the raw CGI exchange.

        Returns:
            `CameraDeviceAttachmentInfo` with sub-device profile, channel,
            lock, elevator, alarm, and smart switch information.
        """

        return fetch_device_attachment_info(
            self._resolve_local_cgi_endpoint(
                port=port,
                scheme=scheme,
                auth_code=auth_code,
                verify_tls=verify_tls,
                debug=debug,
            )
        )

    def get_motion_detection_info(
        self,
        *,
        port: int = 80,
        scheme: str = "http",
        auth_code: str | None = None,
        verify_tls: bool | None = None,
        debug: bool = False,
    ) -> CameraDeviceMotionDetectionInfo:
        """Fetch read-only motion detection settings from `/tdkcgi`.

        This mirrors the original app's `get.motiondetection.info` request and
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
            `CameraDeviceMotionDetectionInfo` with channel id, enabled state,
            sensitivity, and raw motion range string.
        """

        return fetch_motion_detection_info(
            self._resolve_local_cgi_endpoint(
                port=port,
                scheme=scheme,
                auth_code=auth_code,
                verify_tls=verify_tls,
                debug=debug,
            )
        )

    def get_alarm_motion_detection_info(
        self,
        *,
        channel_id: int = 1,
        port: int = 80,
        scheme: str = "http",
        auth_code: str | None = None,
        verify_tls: bool | None = None,
        debug: bool = False,
    ) -> CameraDeviceAlarmMotionDetectionInfo:
        """Fetch read-only alarm motion-detection settings from `/tdkcgi`.

        This mirrors the original app's `get.alarm.motiondetection` request.
        It returns the V-style alarm motion model, including sensitivity,
        pedestrian-detection flag, and optional region grid data.

        Args:
            channel_id: Native alarm channel number sent as `<channel>`.
            port: Camera CGI HTTP(S) port.
            scheme: URL scheme, usually `"http"` for LAN CGI access.
            auth_code: Optional explicit device auth code. When omitted,
                `Camera(..., auth_code=...)` or `AUTH_CODE` from `.env` is
                used. This method never performs cloud login by itself.
            verify_tls: Override TLS certificate verification for HTTPS CGI.
            debug: Enable debug logging for the raw CGI exchange.

        Returns:
            `CameraDeviceAlarmMotionDetectionInfo` with alarm motion settings
            and raw region data.
        """

        return fetch_alarm_motion_detection_info(
            self._resolve_local_cgi_endpoint(
                port=port,
                scheme=scheme,
                auth_code=auth_code,
                verify_tls=verify_tls,
                debug=debug,
            ),
            channel_id=channel_id,
        )

    def get_alarm_video_lost_info(
        self,
        *,
        channel_id: int = 1,
        port: int = 80,
        scheme: str = "http",
        auth_code: str | None = None,
        verify_tls: bool | None = None,
        debug: bool = False,
    ) -> CameraDeviceAlarmVideoLostInfo:
        """Fetch read-only video-lost alarm state from `/tdkcgi`.

        This mirrors the original app's `get.alarm.videolost` request.

        Args:
            channel_id: Native alarm channel number sent as `<channel>`.
            port: Camera CGI HTTP(S) port.
            scheme: URL scheme, usually `"http"` for LAN CGI access.
            auth_code: Optional explicit device auth code. When omitted,
                `Camera(..., auth_code=...)` or `AUTH_CODE` from `.env` is
                used. This method never performs cloud login by itself.
            verify_tls: Override TLS certificate verification for HTTPS CGI.
            debug: Enable debug logging for the raw CGI exchange.

        Returns:
            `CameraDeviceAlarmVideoLostInfo` with the enabled state.
        """

        return fetch_alarm_video_lost_info(
            self._resolve_local_cgi_endpoint(
                port=port,
                scheme=scheme,
                auth_code=auth_code,
                verify_tls=verify_tls,
                debug=debug,
            ),
            channel_id=channel_id,
        )

    def get_alarm_video_shelter_info(
        self,
        *,
        channel_id: int = 1,
        port: int = 80,
        scheme: str = "http",
        auth_code: str | None = None,
        verify_tls: bool | None = None,
        debug: bool = False,
    ) -> CameraDeviceAlarmVideoShelterInfo:
        """Fetch read-only video-shelter alarm state from `/tdkcgi`.

        This mirrors the original app's `get.alarm.videoshelter` request.

        Args:
            channel_id: Native alarm channel number sent as `<channel>`.
            port: Camera CGI HTTP(S) port.
            scheme: URL scheme, usually `"http"` for LAN CGI access.
            auth_code: Optional explicit device auth code. When omitted,
                `Camera(..., auth_code=...)` or `AUTH_CODE` from `.env` is
                used. This method never performs cloud login by itself.
            verify_tls: Override TLS certificate verification for HTTPS CGI.
            debug: Enable debug logging for the raw CGI exchange.

        Returns:
            `CameraDeviceAlarmVideoShelterInfo` with enabled state and
            sensitivity.
        """

        return fetch_alarm_video_shelter_info(
            self._resolve_local_cgi_endpoint(
                port=port,
                scheme=scheme,
                auth_code=auth_code,
                verify_tls=verify_tls,
                debug=debug,
            ),
            channel_id=channel_id,
        )

    def get_alarm_motion_detection_schedule(
        self,
        *,
        channel_id: int = 1,
        port: int = 80,
        scheme: str = "http",
        auth_code: str | None = None,
        verify_tls: bool | None = None,
        debug: bool = False,
    ) -> CameraDeviceAlarmScheduleInfo:
        """Fetch read-only motion-detection alarm schedule from `/tdkcgi`.

        This mirrors the original app's VSU
        `get.alarm.motiondetection.schedule` request with a native
        `<channel>` content field.

        Args:
            channel_id: Native alarm channel number sent as `<channel>`.
            port: Camera CGI HTTP(S) port.
            scheme: URL scheme, usually `"http"` for LAN CGI access.
            auth_code: Optional explicit device auth code. When omitted,
                `Camera(..., auth_code=...)` or `AUTH_CODE` from `.env` is
                used. This method never performs cloud login by itself.
            verify_tls: Override TLS certificate verification for HTTPS CGI.
            debug: Enable debug logging for the raw CGI exchange.

        Returns:
            `CameraDeviceAlarmScheduleInfo` with weekday schedule slots.
        """

        return fetch_alarm_motion_detection_schedule_info(
            self._resolve_local_cgi_endpoint(
                port=port,
                scheme=scheme,
                auth_code=auth_code,
                verify_tls=verify_tls,
                debug=debug,
            ),
            channel_id=channel_id,
        )

    def get_alarm_video_lost_schedule(
        self,
        *,
        channel_id: int = 1,
        port: int = 80,
        scheme: str = "http",
        auth_code: str | None = None,
        verify_tls: bool | None = None,
        debug: bool = False,
    ) -> CameraDeviceAlarmScheduleInfo:
        """Fetch read-only video-lost alarm schedule from `/tdkcgi`.

        This mirrors the original app's `get.alarm.videolost.schedule`
        request.

        Args:
            channel_id: Native alarm channel number sent as `<channel>`.
            port: Camera CGI HTTP(S) port.
            scheme: URL scheme, usually `"http"` for LAN CGI access.
            auth_code: Optional explicit device auth code. When omitted,
                `Camera(..., auth_code=...)` or `AUTH_CODE` from `.env` is
                used. This method never performs cloud login by itself.
            verify_tls: Override TLS certificate verification for HTTPS CGI.
            debug: Enable debug logging for the raw CGI exchange.

        Returns:
            `CameraDeviceAlarmScheduleInfo` with weekday schedule slots.
        """

        return fetch_alarm_video_lost_schedule_info(
            self._resolve_local_cgi_endpoint(
                port=port,
                scheme=scheme,
                auth_code=auth_code,
                verify_tls=verify_tls,
                debug=debug,
            ),
            channel_id=channel_id,
        )

    def get_alarm_video_shelter_schedule(
        self,
        *,
        channel_id: int = 1,
        port: int = 80,
        scheme: str = "http",
        auth_code: str | None = None,
        verify_tls: bool | None = None,
        debug: bool = False,
    ) -> CameraDeviceAlarmScheduleInfo:
        """Fetch read-only video-shelter alarm schedule from `/tdkcgi`.

        This mirrors the original app's `get.alarm.videoshelter.schedule`
        request.

        Args:
            channel_id: Native alarm channel number sent as `<channel>`.
            port: Camera CGI HTTP(S) port.
            scheme: URL scheme, usually `"http"` for LAN CGI access.
            auth_code: Optional explicit device auth code. When omitted,
                `Camera(..., auth_code=...)` or `AUTH_CODE` from `.env` is
                used. This method never performs cloud login by itself.
            verify_tls: Override TLS certificate verification for HTTPS CGI.
            debug: Enable debug logging for the raw CGI exchange.

        Returns:
            `CameraDeviceAlarmScheduleInfo` with weekday schedule slots.
        """

        return fetch_alarm_video_shelter_schedule_info(
            self._resolve_local_cgi_endpoint(
                port=port,
                scheme=scheme,
                auth_code=auth_code,
                verify_tls=verify_tls,
                debug=debug,
            ),
            channel_id=channel_id,
        )

    def get_alarm_input_schedule(
        self,
        *,
        channel_id: int = 1,
        port: int = 80,
        scheme: str = "http",
        auth_code: str | None = None,
        verify_tls: bool | None = None,
        debug: bool = False,
    ) -> CameraDeviceAlarmScheduleInfo:
        """Fetch read-only alarm-input schedule from `/tdkcgi`.

        This mirrors the original app's `get.alarm.alarmin.schedule` request.

        Args:
            channel_id: Native alarm channel number sent as `<channel>`.
            port: Camera CGI HTTP(S) port.
            scheme: URL scheme, usually `"http"` for LAN CGI access.
            auth_code: Optional explicit device auth code. When omitted,
                `Camera(..., auth_code=...)` or `AUTH_CODE` from `.env` is
                used. This method never performs cloud login by itself.
            verify_tls: Override TLS certificate verification for HTTPS CGI.
            debug: Enable debug logging for the raw CGI exchange.

        Returns:
            `CameraDeviceAlarmScheduleInfo` with weekday schedule slots.
        """

        return fetch_alarm_input_schedule_info(
            self._resolve_local_cgi_endpoint(
                port=port,
                scheme=scheme,
                auth_code=auth_code,
                verify_tls=verify_tls,
                debug=debug,
            ),
            channel_id=channel_id,
        )

    def get_human_trace_info(
        self,
        *,
        port: int = 80,
        scheme: str = "http",
        auth_code: str | None = None,
        verify_tls: bool | None = None,
        debug: bool = False,
    ) -> CameraDeviceHumanTraceInfo:
        """Fetch read-only human-trace detection state from `/tdkcgi`.

        This mirrors the original app's `get.humantrace.info` request and
        reads the boolean `<enabled>` field from the response.

        Args:
            port: Camera CGI HTTP(S) port.
            scheme: URL scheme, usually `"http"` for LAN CGI access.
            auth_code: Optional explicit device auth code. When omitted,
                `Camera(..., auth_code=...)` or `AUTH_CODE` from `.env` is
                used. This method never performs cloud login by itself.
            verify_tls: Override TLS certificate verification for HTTPS CGI.
            debug: Enable debug logging for the raw CGI exchange.

        Returns:
            `CameraDeviceHumanTraceInfo` with the enabled state and raw
            response content.
        """

        return fetch_human_trace_info(
            self._resolve_local_cgi_endpoint(
                port=port,
                scheme=scheme,
                auth_code=auth_code,
                verify_tls=verify_tls,
                debug=debug,
            )
        )

    def get_move_detection_info(
        self,
        *,
        port: int = 80,
        scheme: str = "http",
        auth_code: str | None = None,
        verify_tls: bool | None = None,
        debug: bool = False,
    ) -> CameraDeviceMoveDetectionInfo:
        """Fetch read-only move-detection state from `/tdkcgi`.

        This mirrors the original app's `get.movedetection.info` request and
        reads the boolean `<enabled>` field from the response.

        Args:
            port: Camera CGI HTTP(S) port.
            scheme: URL scheme, usually `"http"` for LAN CGI access.
            auth_code: Optional explicit device auth code. When omitted,
                `Camera(..., auth_code=...)` or `AUTH_CODE` from `.env` is
                used. This method never performs cloud login by itself.
            verify_tls: Override TLS certificate verification for HTTPS CGI.
            debug: Enable debug logging for the raw CGI exchange.

        Returns:
            `CameraDeviceMoveDetectionInfo` with the enabled state and raw
            response content.
        """

        return fetch_move_detection_info(
            self._resolve_local_cgi_endpoint(
                port=port,
                scheme=scheme,
                auth_code=auth_code,
                verify_tls=verify_tls,
                debug=debug,
            )
        )

    def get_fps_info(
        self,
        *,
        channel_id: int = -1,
        stream_id: int = -1,
        port: int = 80,
        scheme: str = "http",
        auth_code: str | None = None,
        verify_tls: bool | None = None,
        debug: bool = False,
    ) -> CameraDeviceFpsInfo:
        """Fetch read-only FPS settings from `/tdkcgi`.

        This mirrors the original app's `get.encode.fps` request. The native
        app accepts `-1` for `channel_id` and `stream_id` to request all
        channels/streams.

        Args:
            channel_id: Native zero-based channel index, or `-1` for all.
            stream_id: Native zero-based stream index, or `-1` for all.
            port: Camera CGI HTTP(S) port.
            scheme: URL scheme, usually `"http"` for LAN CGI access.
            auth_code: Optional explicit device auth code. When omitted,
                `Camera(..., auth_code=...)` or `AUTH_CODE` from `.env` is
                used. This method never performs cloud login by itself.
            verify_tls: Override TLS certificate verification for HTTPS CGI.
            debug: Enable debug logging for the raw CGI exchange.

        Returns:
            `CameraDeviceFpsInfo` with channel/stream FPS entries.
        """

        return fetch_fps_info(
            self._resolve_local_cgi_endpoint(
                port=port,
                scheme=scheme,
                auth_code=auth_code,
                verify_tls=verify_tls,
                debug=debug,
            ),
            channel_id=channel_id,
            stream_id=stream_id,
        )

    def get_json_fps_mode_info(
        self,
        *,
        port: int = 80,
        scheme: str = "http",
        auth_code: str | None = None,
        verify_tls: bool | None = None,
        debug: bool = False,
    ) -> CameraDeviceJsonFpsModeInfo:
        """Fetch read-only FPS mode from JSON `/tdkcgi`.

        This mirrors the original app's `get.fps.mode` JSON request. It is a
        direct HTTP CGI call to `Camera(..., device_host=...)`, not a cloud or
        live-preview call.

        Args:
            port: Camera CGI HTTP(S) port.
            scheme: URL scheme, usually `"http"` for LAN CGI access.
            auth_code: Optional explicit device auth code. When omitted,
                `Camera(..., auth_code=...)` or `AUTH_CODE` from `.env` is
                used. This method never performs cloud login by itself.
            verify_tls: Override TLS certificate verification for HTTPS CGI.
            debug: Enable debug logging for the raw CGI exchange.

        Returns:
            `CameraDeviceJsonFpsModeInfo` with the native JSON FPS mode.
        """

        return fetch_json_fps_mode_info(
            self._resolve_local_cgi_endpoint(
                port=port,
                scheme=scheme,
                auth_code=auth_code,
                verify_tls=verify_tls,
                debug=debug,
            )
        )

    def get_audio_volume_info(
        self,
        *,
        port: int = 80,
        scheme: str = "http",
        auth_code: str | None = None,
        verify_tls: bool | None = None,
        debug: bool = False,
    ) -> CameraDeviceAudioVolumeInfo:
        """Fetch read-only audio output volume from JSON `/tdkcgi`.

        This mirrors the original app's `get.audio.outvolume` JSON request and
        exposes prompt/talk volume ranges when the device reports them.

        Args:
            port: Camera CGI HTTP(S) port.
            scheme: URL scheme, usually `"http"` for LAN CGI access.
            auth_code: Optional explicit device auth code. When omitted,
                `Camera(..., auth_code=...)` or `AUTH_CODE` from `.env` is
                used. This method never performs cloud login by itself.
            verify_tls: Override TLS certificate verification for HTTPS CGI.
            debug: Enable debug logging for the raw CGI exchange.

        Returns:
            `CameraDeviceAudioVolumeInfo` with prompt and talk volume ranges.
        """

        return fetch_audio_volume_info(
            self._resolve_local_cgi_endpoint(
                port=port,
                scheme=scheme,
                auth_code=auth_code,
                verify_tls=verify_tls,
                debug=debug,
            )
        )

    def get_audio_session_info(
        self,
        *,
        port: int = 80,
        scheme: str = "http",
        auth_code: str | None = None,
        verify_tls: bool | None = None,
        debug: bool = False,
    ) -> CameraDeviceAudioSessionInfo:
        """Fetch read-only audio file session from JSON `/tdkcgi`.

        This mirrors the original app's `get.audio.session` JSON request. The
        native client uses the returned session and file id for voice-message
        audio file operations; this method only reads and returns the values.

        Args:
            port: Camera CGI HTTP(S) port.
            scheme: URL scheme, usually `"http"` for LAN CGI access.
            auth_code: Optional explicit device auth code. When omitted,
                `Camera(..., auth_code=...)` or `AUTH_CODE` from `.env` is
                used. This method never performs cloud login by itself.
            verify_tls: Override TLS certificate verification for HTTPS CGI.
            debug: Enable debug logging for the raw CGI exchange.

        Returns:
            `CameraDeviceAudioSessionInfo` with session and file id values.
        """

        return fetch_audio_session_info(
            self._resolve_local_cgi_endpoint(
                port=port,
                scheme=scheme,
                auth_code=auth_code,
                verify_tls=verify_tls,
                debug=debug,
            )
        )

    def get_hardware_info(
        self,
        *,
        port: int = 80,
        scheme: str = "http",
        auth_code: str | None = None,
        verify_tls: bool | None = None,
        debug: bool = False,
    ) -> CameraDeviceHardwareInfo:
        """Fetch read-only battery and charge state from JSON `/tdkcgi`.

        This mirrors the original app's `getHWInfo` JSON request. The returned
        temperature follows the native client conversion:
        `voltameterTemp / 10.0`.

        Args:
            port: Camera CGI HTTP(S) port.
            scheme: URL scheme, usually `"http"` for LAN CGI access.
            auth_code: Optional explicit device auth code. When omitted,
                `Camera(..., auth_code=...)` or `AUTH_CODE` from `.env` is
                used. This method never performs cloud login by itself.
            verify_tls: Override TLS certificate verification for HTTPS CGI.
            debug: Enable debug logging for the raw CGI exchange.

        Returns:
            `CameraDeviceHardwareInfo` with battery, charge source, and charge
            status values.
        """

        return fetch_hardware_info(
            self._resolve_local_cgi_endpoint(
                port=port,
                scheme=scheme,
                auth_code=auth_code,
                verify_tls=verify_tls,
                debug=debug,
            )
        )

    def get_light_info(
        self,
        *,
        port: int = 80,
        scheme: str = "http",
        auth_code: str | None = None,
        verify_tls: bool | None = None,
        debug: bool = False,
    ) -> CameraDeviceLightInfo:
        """Fetch read-only room-light topology from JSON `/tdkcgi`.

        This mirrors the original app's `get.light.info` JSON request and
        exposes rooms with their light names, status values, and brightness.

        Args:
            port: Camera CGI HTTP(S) port.
            scheme: URL scheme, usually `"http"` for LAN CGI access.
            auth_code: Optional explicit device auth code. When omitted,
                `Camera(..., auth_code=...)` or `AUTH_CODE` from `.env` is
                used. This method never performs cloud login by itself.
            verify_tls: Override TLS certificate verification for HTTPS CGI.
            debug: Enable debug logging for the raw CGI exchange.

        Returns:
            `CameraDeviceLightInfo` with room and light entries.
        """

        return fetch_light_info(
            self._resolve_local_cgi_endpoint(
                port=port,
                scheme=scheme,
                auth_code=auth_code,
                verify_tls=verify_tls,
                debug=debug,
            )
        )

    def get_pir_config_info(
        self,
        *,
        port: int = 80,
        scheme: str = "http",
        auth_code: str | None = None,
        verify_tls: bool | None = None,
        debug: bool = False,
    ) -> CameraDevicePirConfigInfo:
        """Fetch read-only PIR sensor configuration from JSON `/tdkcgi`.

        This mirrors the original app's `getPIRCfg` JSON request and exposes
        the enable flag, sensitivity, record-link flag, and schedule slots.

        Args:
            port: Camera CGI HTTP(S) port.
            scheme: URL scheme, usually `"http"` for LAN CGI access.
            auth_code: Optional explicit device auth code. When omitted,
                `Camera(..., auth_code=...)` or `AUTH_CODE` from `.env` is
                used. This method never performs cloud login by itself.
            verify_tls: Override TLS certificate verification for HTTPS CGI.
            debug: Enable debug logging for the raw CGI exchange.

        Returns:
            `CameraDevicePirConfigInfo` with PIR state and schedule entries.
        """

        return fetch_pir_config_info(
            self._resolve_local_cgi_endpoint(
                port=port,
                scheme=scheme,
                auth_code=auth_code,
                verify_tls=verify_tls,
                debug=debug,
            )
        )

    def get_third_party_push_info(
        self,
        *,
        port: int = 80,
        scheme: str = "http",
        auth_code: str | None = None,
        verify_tls: bool | None = None,
        debug: bool = False,
    ) -> CameraDeviceThirdPartyPushInfo:
        """Fetch read-only third-party push settings from JSON `/tdkcgi`.

        This mirrors the original app's `get.thirdpartypush.info` JSON request
        and exposes the configured account, area code, push enable flag,
        event types, supported event types, and schedule.

        Args:
            port: Camera CGI HTTP(S) port.
            scheme: URL scheme, usually `"http"` for LAN CGI access.
            auth_code: Optional explicit device auth code. When omitted,
                `Camera(..., auth_code=...)` or `AUTH_CODE` from `.env` is
                used. This method never performs cloud login by itself.
            verify_tls: Override TLS certificate verification for HTTPS CGI.
            debug: Enable debug logging for the raw CGI exchange.

        Returns:
            `CameraDeviceThirdPartyPushInfo` with third-party push settings.
        """

        return fetch_third_party_push_info(
            self._resolve_local_cgi_endpoint(
                port=port,
                scheme=scheme,
                auth_code=auth_code,
                verify_tls=verify_tls,
                debug=debug,
            )
        )

    def get_babysitter_state_info(
        self,
        *,
        port: int = 80,
        scheme: str = "http",
        auth_code: str | None = None,
        verify_tls: bool | None = None,
        debug: bool = False,
    ) -> CameraDeviceBabysitterStateInfo:
        """Fetch read-only babysitter mode state from JSON `/tdkcgi`.

        This mirrors the original app's `get.babysitter` JSON request.

        Args:
            port: Camera CGI HTTP(S) port.
            scheme: URL scheme, usually `"http"` for LAN CGI access.
            auth_code: Optional explicit device auth code. When omitted,
                `Camera(..., auth_code=...)` or `AUTH_CODE` from `.env` is
                used. This method never performs cloud login by itself.
            verify_tls: Override TLS certificate verification for HTTPS CGI.
            debug: Enable debug logging for the raw CGI exchange.

        Returns:
            `CameraDeviceBabysitterStateInfo` with the native mode value.
        """

        return fetch_babysitter_state_info(
            self._resolve_local_cgi_endpoint(
                port=port,
                scheme=scheme,
                auth_code=auth_code,
                verify_tls=verify_tls,
                debug=debug,
            )
        )

    def get_smart_switch_info(
        self,
        *,
        port: int = 80,
        scheme: str = "http",
        auth_code: str | None = None,
        verify_tls: bool | None = None,
        debug: bool = False,
    ) -> CameraDeviceSmartSwitchInfo:
        """Fetch read-only smart-switch topology from JSON `/tdkcgi`.

        This mirrors the original app's `get.smartswitch.info` JSON request
        and exposes rooms, switches, switch online state, and channels.

        Args:
            port: Camera CGI HTTP(S) port.
            scheme: URL scheme, usually `"http"` for LAN CGI access.
            auth_code: Optional explicit device auth code. When omitted,
                `Camera(..., auth_code=...)` or `AUTH_CODE` from `.env` is
                used. This method never performs cloud login by itself.
            verify_tls: Override TLS certificate verification for HTTPS CGI.
            debug: Enable debug logging for the raw CGI exchange.

        Returns:
            `CameraDeviceSmartSwitchInfo` with room, switch, and channel
            entries.
        """

        return fetch_smart_switch_info(
            self._resolve_local_cgi_endpoint(
                port=port,
                scheme=scheme,
                auth_code=auth_code,
                verify_tls=verify_tls,
                debug=debug,
            )
        )

    def get_lock_status_info(
        self,
        *,
        port: int = 80,
        scheme: str = "http",
        auth_code: str | None = None,
        verify_tls: bool | None = None,
        debug: bool = False,
    ) -> CameraDeviceLockStatusInfo:
        """Fetch read-only lock status from JSON `/tdkcgi`.

        This mirrors the original app's `get.lock.status` JSON request and
        exposes lock ids, display names, and unlock time ranges when the device
        reports them.

        Args:
            port: Camera CGI HTTP(S) port.
            scheme: URL scheme, usually `"http"` for LAN CGI access.
            auth_code: Optional explicit device auth code. When omitted,
                `Camera(..., auth_code=...)` or `AUTH_CODE` from `.env` is
                used. This method never performs cloud login by itself.
            verify_tls: Override TLS certificate verification for HTTPS CGI.
            debug: Enable debug logging for the raw CGI exchange.

        Returns:
            `CameraDeviceLockStatusInfo` with reported lock entries.
        """

        return fetch_lock_status_info(
            self._resolve_local_cgi_endpoint(
                port=port,
                scheme=scheme,
                auth_code=auth_code,
                verify_tls=verify_tls,
                debug=debug,
            )
        )

    def get_floodlight_switch_info(
        self,
        *,
        port: int = 80,
        scheme: str = "http",
        auth_code: str | None = None,
        verify_tls: bool | None = None,
        debug: bool = False,
    ) -> CameraDeviceFloodlightSwitchInfo:
        """Fetch read-only floodlight switch state from JSON `/tdkcgi`.

        This mirrors the original app's `get.floodlight.switch` JSON request.
        It keeps the raw firmware status string and also exposes the native
        status code mapping: `on=0`, `off=1`, `auto=2`.

        Args:
            port: Camera CGI HTTP(S) port.
            scheme: URL scheme, usually `"http"` for LAN CGI access.
            auth_code: Optional explicit device auth code. When omitted,
                `Camera(..., auth_code=...)` or `AUTH_CODE` from `.env` is
                used. This method never performs cloud login by itself.
            verify_tls: Override TLS certificate verification for HTTPS CGI.
            debug: Enable debug logging for the raw CGI exchange.

        Returns:
            `CameraDeviceFloodlightSwitchInfo` with floodlight entries.
        """

        return fetch_floodlight_switch_info(
            self._resolve_local_cgi_endpoint(
                port=port,
                scheme=scheme,
                auth_code=auth_code,
                verify_tls=verify_tls,
                debug=debug,
            )
        )

    def get_floodlight_schedule_info(
        self,
        *,
        port: int = 80,
        scheme: str = "http",
        auth_code: str | None = None,
        verify_tls: bool | None = None,
        debug: bool = False,
    ) -> CameraDeviceFloodlightScheduleInfo:
        """Fetch read-only floodlight schedule from JSON `/tdkcgi`.

        This mirrors the original app's custom `get.floodlight.schedule`
        request. It exposes sunrise/sunset times and per-week floodlight plans.
        Native time mode mapping is preserved as `sunrise=0`, `sunset=1`,
        `time=2`, and unknown modes as `-1`.

        Args:
            port: Camera CGI HTTP(S) port.
            scheme: URL scheme, usually `"http"` for LAN CGI access.
            auth_code: Optional explicit device auth code. When omitted,
                `Camera(..., auth_code=...)` or `AUTH_CODE` from `.env` is
                used. This method never performs cloud login by itself.
            verify_tls: Override TLS certificate verification for HTTPS CGI.
            debug: Enable debug logging for the raw CGI exchange.

        Returns:
            `CameraDeviceFloodlightScheduleInfo` with schedule days and plans.
        """

        return fetch_floodlight_schedule_info(
            self._resolve_local_cgi_endpoint(
                port=port,
                scheme=scheme,
                auth_code=auth_code,
                verify_tls=verify_tls,
                debug=debug,
            )
        )

    def get_city_coordinate_info(
        self,
        *,
        port: int = 80,
        scheme: str = "http",
        auth_code: str | None = None,
        verify_tls: bool | None = None,
        debug: bool = False,
    ) -> CameraDeviceCityCoordinateInfo:
        """Fetch read-only city coordinates from JSON `/tdkcgi`.

        This mirrors the original app's custom `get.city.coordinate` request.
        The response contains latitude, longitude, and optional sunrise/sunset
        strings that the native client can use as a fallback for floodlight
        schedule sun times.

        Args:
            port: Camera CGI HTTP(S) port.
            scheme: URL scheme, usually `"http"` for LAN CGI access.
            auth_code: Optional explicit device auth code. When omitted,
                `Camera(..., auth_code=...)` or `AUTH_CODE` from `.env` is
                used. This method never performs cloud login by itself.
            verify_tls: Override TLS certificate verification for HTTPS CGI.
            debug: Enable debug logging for the raw CGI exchange.

        Returns:
            `CameraDeviceCityCoordinateInfo` with coordinates and sun times.
        """

        return fetch_city_coordinate_info(
            self._resolve_local_cgi_endpoint(
                port=port,
                scheme=scheme,
                auth_code=auth_code,
                verify_tls=verify_tls,
                debug=debug,
            )
        )

    def get_voice_message_info(
        self,
        *,
        port: int = 80,
        scheme: str = "http",
        auth_code: str | None = None,
        verify_tls: bool | None = None,
        debug: bool = False,
    ) -> CameraDeviceVoiceMessageInfo:
        """Fetch read-only voice-message settings from JSON `/tdkcgi`.

        This mirrors the original app's `get.voice.message` JSON request and
        exposes the selected prompt file, mode, and available voice files.

        Args:
            port: Camera CGI HTTP(S) port.
            scheme: URL scheme, usually `"http"` for LAN CGI access.
            auth_code: Optional explicit device auth code. When omitted,
                `Camera(..., auth_code=...)` or `AUTH_CODE` from `.env` is
                used. This method never performs cloud login by itself.
            verify_tls: Override TLS certificate verification for HTTPS CGI.
            debug: Enable debug logging for the raw CGI exchange.

        Returns:
            `CameraDeviceVoiceMessageInfo` with voice prompt configuration.
        """

        return fetch_voice_message_info(
            self._resolve_local_cgi_endpoint(
                port=port,
                scheme=scheme,
                auth_code=auth_code,
                verify_tls=verify_tls,
                debug=debug,
            )
        )

    def get_ptz_state(
        self,
        *,
        port: int = 80,
        scheme: str = "http",
        auth_code: str | None = None,
        verify_tls: bool | None = None,
        debug: bool = False,
    ) -> CameraDevicePtzStateInfo:
        """Fetch read-only PTZ position state from `/tdkcgi`.

        This mirrors the original app's `get.ptz.position` request and uses
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
            `CameraDevicePtzStateInfo` with current X/Y position and native
            min/max ranges.
        """

        return fetch_ptz_state_info(
            self._resolve_local_cgi_endpoint(
                port=port,
                scheme=scheme,
                auth_code=auth_code,
                verify_tls=verify_tls,
                debug=debug,
            )
        )

    def get_ptz_presets(
        self,
        *,
        port: int = 80,
        scheme: str = "http",
        auth_code: str | None = None,
        verify_tls: bool | None = None,
        debug: bool = False,
    ) -> CameraDevicePtzPresetInfo:
        """Fetch read-only PTZ preset list from `/tdkcgi`.

        This mirrors the original app's `get.ptz.preset` request and uses
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
            `CameraDevicePtzPresetInfo` with preset ids and names.
        """

        return fetch_ptz_preset_info(
            self._resolve_local_cgi_endpoint(
                port=port,
                scheme=scheme,
                auth_code=auth_code,
                verify_tls=verify_tls,
                debug=debug,
            )
        )

    def get_smart_light_info(
        self,
        *,
        room: int = 1,
        port: int = 80,
        scheme: str = "http",
        auth_code: str | None = None,
        verify_tls: bool | None = None,
        debug: bool = False,
    ) -> CameraDeviceSmartLightInfo:
        """Fetch read-only smart-light room state from `/tdkcgi`.

        This mirrors the original app's `get.smart.lightinfo` request. The
        native request sends a single `<room>` value and returns zero or more
        `<lightinfo>` entries.

        Args:
            room: Native room number to query. The original app passes this
                value directly as `<room>`.
            port: Camera CGI HTTP(S) port.
            scheme: URL scheme, usually `"http"` for LAN CGI access.
            auth_code: Optional explicit device auth code. When omitted,
                `Camera(..., auth_code=...)` or `AUTH_CODE` from `.env` is
                used. This method never performs cloud login by itself.
            verify_tls: Override TLS certificate verification for HTTPS CGI.
            debug: Enable debug logging for the raw CGI exchange.

        Returns:
            `CameraDeviceSmartLightInfo` with room number, reported light
            count, and individual light entries.
        """

        return fetch_smart_light_info(
            self._resolve_local_cgi_endpoint(
                port=port,
                scheme=scheme,
                auth_code=auth_code,
                verify_tls=verify_tls,
                debug=debug,
            ),
            room=room,
        )

    def get_sound_light_info(
        self,
        *,
        channel_id: int = 1,
        port: int = 80,
        scheme: str = "http",
        auth_code: str | None = None,
        verify_tls: bool | None = None,
        debug: bool = False,
    ) -> CameraDeviceSoundLightInfo:
        """Fetch read-only sound-and-light one-key control state.

        This mirrors the original app's `get.soundandlight.state` request. The
        native request sends the channel directly as `<channel>...</channel>`
        and reads `SoundAndLightOneKeyCtrl/CtrlState` from the response.

        Args:
            channel_id: Native channel value to query. The original app passes
                this value directly as `<channel>`.
            port: Camera CGI HTTP(S) port.
            scheme: URL scheme, usually `"http"` for LAN CGI access.
            auth_code: Optional explicit device auth code. When omitted,
                `Camera(..., auth_code=...)` or `AUTH_CODE` from `.env` is
                used. This method never performs cloud login by itself.
            verify_tls: Override TLS certificate verification for HTTPS CGI.
            debug: Enable debug logging for the raw CGI exchange.

        Returns:
            `CameraDeviceSoundLightInfo` with per-channel one-key control
            state entries.
        """

        return fetch_sound_light_info(
            self._resolve_local_cgi_endpoint(
                port=port,
                scheme=scheme,
                auth_code=auth_code,
                verify_tls=verify_tls,
                debug=debug,
            ),
            channel_id=channel_id,
        )

    def get_device_profile(
        self,
        *,
        port: int = 80,
        scheme: str = "http",
        auth_code: str | None = None,
        verify_tls: bool | None = None,
        debug: bool = False,
    ) -> CameraDeviceProfile:
        """Fetch an aggregated read-only local CGI device profile.

        This calls the known read-only `/tdkcgi` commands and returns both the
        individual typed responses and command-level status lists. It is useful
        when firmware supports only a subset of local CGI commands.

        Args:
            port: Camera CGI HTTP(S) port.
            scheme: URL scheme, usually `"http"` for LAN CGI access.
            auth_code: Optional explicit device auth code. When omitted,
                `Camera(..., auth_code=...)` or `AUTH_CODE` from `.env` is
                used. This method never performs cloud login by itself.
            verify_tls: Override TLS certificate verification for HTTPS CGI.
            debug: Enable debug logging for the raw CGI exchange.

        Returns:
            `CameraDeviceProfile` with all read-only responses and command
            support status.
        """

        return fetch_device_profile(
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

    def get_tf_card_info(
        self,
        *,
        port: int = 80,
        scheme: str = "http",
        auth_code: str | None = None,
        verify_tls: bool | None = None,
        debug: bool = False,
    ) -> CameraDeviceTfCardInfo:
        """Fetch read-only TF-card status from `/tdkcgi`.

        This mirrors the original app's `get.tfcard.info` request and uses
        `Camera(..., device_host=...)`. It reports aggregate card capacity,
        formatting state, and per-disk status values when firmware provides
        them.

        Args:
            port: Camera CGI HTTP(S) port.
            scheme: URL scheme, usually `"http"` for LAN CGI access.
            auth_code: Optional explicit device auth code. When omitted,
                `Camera(..., auth_code=...)` or `AUTH_CODE` from `.env` is
                used. This method never performs cloud login by itself.
            verify_tls: Override TLS certificate verification for HTTPS CGI.
            debug: Enable debug logging for the raw CGI exchange.

        Returns:
            `CameraDeviceTfCardInfo` with formatting state, totals, and TF-card
            disk entries.
        """

        return fetch_tf_card_info(
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

    def get_stream_key_info(
        self,
        *,
        port: int = 80,
        scheme: str = "http",
        auth_code: str | None = None,
        verify_tls: bool | None = None,
        debug: bool = False,
    ) -> CameraDeviceStreamKeyInfo:
        """Fetch read-only stream key metadata from `/tdkcgi`.

        This mirrors the original app's `get.device.streamkey` request and
        uses `Camera(..., device_host=...)`. It does not open a preview session
        and does not perform cloud login by itself.

        Args:
            port: Camera CGI HTTP(S) port.
            scheme: URL scheme, usually `"http"` for LAN CGI access.
            auth_code: Optional explicit device auth code. When omitted,
                `Camera(..., auth_code=...)` or `AUTH_CODE` from `.env` is
                used.
            verify_tls: Override TLS certificate verification for HTTPS CGI.
            debug: Enable debug logging for the raw CGI exchange.

        Returns:
            `CameraDeviceStreamKeyInfo` with key, TDC, and sync-time fields.
        """

        return fetch_stream_key_info(
            self._resolve_local_cgi_endpoint(
                port=port,
                scheme=scheme,
                auth_code=auth_code,
                verify_tls=verify_tls,
                debug=debug,
            )
        )

    def get_qr_code_info(
        self,
        *,
        port: int = 80,
        scheme: str = "http",
        auth_code: str | None = None,
        verify_tls: bool | None = None,
        debug: bool = False,
    ) -> CameraDeviceQrCodeInfo:
        """Fetch read-only device QR code from `/tdkcgi`.

        This mirrors the original app's `get.device.qrcode` request and uses
        `Camera(..., device_host=...)`. It does not open a preview session and
        does not perform cloud login by itself.

        Args:
            port: Camera CGI HTTP(S) port.
            scheme: URL scheme, usually `"http"` for LAN CGI access.
            auth_code: Optional explicit device auth code. When omitted,
                `Camera(..., auth_code=...)` or `AUTH_CODE` from `.env` is
                used.
            verify_tls: Override TLS certificate verification for HTTPS CGI.
            debug: Enable debug logging for the raw CGI exchange.

        Returns:
            `CameraDeviceQrCodeInfo` with the QR code string and raw response.
        """

        return fetch_qr_code_info(
            self._resolve_local_cgi_endpoint(
                port=port,
                scheme=scheme,
                auth_code=auth_code,
                verify_tls=verify_tls,
                debug=debug,
            )
        )

    def get_record_config_info(
        self,
        *,
        channel_id: int = 1,
        port: int = 80,
        scheme: str = "http",
        auth_code: str | None = None,
        verify_tls: bool | None = None,
        debug: bool = False,
    ) -> CameraDeviceRecordConfigInfo:
        """Fetch read-only recording configuration from `/tdkcgi`.

        This mirrors the original app's `get.record.config` request and uses
        `Camera(..., device_host=...)`. It reports the record stream, pre-record
        setting, packet length, record-control mode, and weekly schedule
        entries for one channel.

        Args:
            channel_id: Device channel id sent in the native `<channel>` field.
            port: Camera CGI HTTP(S) port.
            scheme: URL scheme, usually `"http"` for LAN CGI access.
            auth_code: Optional explicit device auth code. When omitted,
                `Camera(..., auth_code=...)` or `AUTH_CODE` from `.env` is
                used.
            verify_tls: Override TLS certificate verification for HTTPS CGI.
            debug: Enable debug logging for the raw CGI exchange.

        Returns:
            `CameraDeviceRecordConfigInfo` with record mode and per-day
            schedule slots.
        """

        return fetch_record_config_info(
            self._resolve_local_cgi_endpoint(
                port=port,
                scheme=scheme,
                auth_code=auth_code,
                verify_tls=verify_tls,
                debug=debug,
            ),
            channel_id=channel_id,
        )

    def get_record_session_info(
        self,
        *,
        start_time: str,
        end_time: str,
        channel_id: int = 1,
        file_type: str = "all",
        occur_type: str = "all",
        stream: str = "all",
        port: int = 80,
        scheme: str = "http",
        auth_code: str | None = None,
        verify_tls: bool | None = None,
        debug: bool = False,
    ) -> CameraDeviceRecordSessionInfo:
        """Open a read-only archive search session via `/tdkcgi`.

        This mirrors the original app's `get.record.session` request. The
        returned session id is used by the native client for follow-up
        `get.record.message` calls that stream the actual recording list.

        Args:
            start_time: CGI archive search start time string.
            end_time: CGI archive search end time string.
            channel_id: Device channel id sent in the native `<channel>` field.
            file_type: Native CGI file type string, usually `"all"`.
            occur_type: Native CGI occurrence type string, usually `"all"`.
            stream: Native CGI stream selector: `"main"`, `"sub"`, or `"all"`.
            port: Camera CGI HTTP(S) port.
            scheme: URL scheme, usually `"http"` for LAN CGI access.
            auth_code: Optional explicit device auth code. When omitted,
                `Camera(..., auth_code=...)` or `AUTH_CODE` from `.env` is
                used.
            verify_tls: Override TLS certificate verification for HTTPS CGI.
            debug: Enable debug logging for the raw CGI exchange.

        Returns:
            `CameraDeviceRecordSessionInfo` with the archive search session id.
        """

        return fetch_record_session_info(
            self._resolve_local_cgi_endpoint(
                port=port,
                scheme=scheme,
                auth_code=auth_code,
                verify_tls=verify_tls,
                debug=debug,
            ),
            start_time=start_time,
            end_time=end_time,
            channel_id=channel_id,
            file_type=file_type,
            occur_type=occur_type,
            stream=stream,
        )

    def get_record_message_info(
        self,
        *,
        session_id: str,
        port: int = 80,
        scheme: str = "http",
        auth_code: str | None = None,
        verify_tls: bool | None = None,
        debug: bool = False,
    ) -> CameraDeviceRecordMessageInfo:
        """Fetch one read-only archive message page via `/tdkcgi`.

        This mirrors the original app's `get.record.message` request. Pass the
        session id returned by `get_record_session_info()`. Firmware may return
        a paging/status value; callers can inspect `result` to decide whether
        another `get.record.message` request is needed.

        Args:
            session_id: Archive search session id returned by
                `get_record_session_info()`.
            port: Camera CGI HTTP(S) port.
            scheme: URL scheme, usually `"http"` for LAN CGI access.
            auth_code: Optional explicit device auth code. When omitted,
                `Camera(..., auth_code=...)` or `AUTH_CODE` from `.env` is
                used.
            verify_tls: Override TLS certificate verification for HTTPS CGI.
            debug: Enable debug logging for the raw CGI exchange.

        Returns:
            `CameraDeviceRecordMessageInfo` with parsed archive file entries.
        """

        return fetch_record_message_info(
            self._resolve_local_cgi_endpoint(
                port=port,
                scheme=scheme,
                auth_code=auth_code,
                verify_tls=verify_tls,
                debug=debug,
            ),
            session_id=session_id,
        )

    def list_record_files(
        self,
        *,
        start_time: str,
        end_time: str,
        channel_id: int = 1,
        file_type: str = "all",
        occur_type: str = "all",
        stream: str = "all",
        max_pages: int = 32,
        port: int = 80,
        scheme: str = "http",
        auth_code: str | None = None,
        verify_tls: bool | None = None,
        debug: bool = False,
    ) -> CameraDeviceRecordListInfo:
        """Fetch archive file entries using the native CGI paging sequence.

        This is a convenience wrapper around `get.record.session` followed by
        repeated `get.record.message` requests. It mirrors the original app's
        archive-list flow, but stops after `max_pages` pages if firmware never
        reports native completion.

        Args:
            start_time: CGI archive search start time string.
            end_time: CGI archive search end time string.
            channel_id: Device channel id sent in the native `<channel>` field.
            file_type: Native CGI file type string, usually `"all"`.
            occur_type: Native CGI occurrence type string, usually `"all"`.
            stream: Native CGI stream selector: `"main"`, `"sub"`, or `"all"`.
            max_pages: Safety cap for repeated `get.record.message` requests.
            port: Camera CGI HTTP(S) port.
            scheme: URL scheme, usually `"http"` for LAN CGI access.
            auth_code: Optional explicit device auth code. When omitted,
                `Camera(..., auth_code=...)` or `AUTH_CODE` from `.env` is
                used.
            verify_tls: Override TLS certificate verification for HTTPS CGI.
            debug: Enable debug logging for the raw CGI exchange.

        Returns:
            `CameraDeviceRecordListInfo` with the archive session id, fetched
            pages, records, and completion status.
        """

        return fetch_record_list_info(
            self._resolve_local_cgi_endpoint(
                port=port,
                scheme=scheme,
                auth_code=auth_code,
                verify_tls=verify_tls,
                debug=debug,
            ),
            start_time=start_time,
            end_time=end_time,
            channel_id=channel_id,
            file_type=file_type,
            occur_type=occur_type,
            stream=stream,
            max_pages=max_pages,
        )

    def get_record_alarm_info(
        self,
        *,
        timestamp: str,
        channel_id: int = 1,
        file_type: str = "all",
        occur_type: str = "all",
        stream: str = "all",
        alarm_type: int | None = None,
        alarm_id: str | None = None,
        port: int = 80,
        scheme: str = "http",
        auth_code: str | None = None,
        verify_tls: bool | None = None,
        debug: bool = False,
    ) -> CameraDeviceRecordAlarmInfo:
        """Fetch alarm-linked archive records via `/tdkcgi`.

        This mirrors the original app's `get.record.alarmrecord` request. It
        uses a single alarm timestamp plus optional alarm identifiers, then
        parses the returned records with the same native record-list shape used
        by archive pages.

        Args:
            timestamp: Alarm timestamp string sent in the native `<timestamp>`
                field.
            channel_id: Device channel id sent in the native `<channel>` field.
            file_type: Native CGI file type string, usually `"all"`.
            occur_type: Native CGI occurrence type string, usually `"all"`.
            stream: Native CGI stream selector: `"main"`, `"sub"`, or `"all"`.
            alarm_type: Optional native alarm event type.
            alarm_id: Optional native alarm id.
            port: Camera CGI HTTP(S) port.
            scheme: URL scheme, usually `"http"` for LAN CGI access.
            auth_code: Optional explicit device auth code. When omitted,
                `Camera(..., auth_code=...)` or `AUTH_CODE` from `.env` is
                used.
            verify_tls: Override TLS certificate verification for HTTPS CGI.
            debug: Enable debug logging for the raw CGI exchange.

        Returns:
            `CameraDeviceRecordAlarmInfo` with parsed alarm-linked archive file
            entries.
        """

        return fetch_record_alarm_info(
            self._resolve_local_cgi_endpoint(
                port=port,
                scheme=scheme,
                auth_code=auth_code,
                verify_tls=verify_tls,
                debug=debug,
            ),
            timestamp=timestamp,
            channel_id=channel_id,
            file_type=file_type,
            occur_type=occur_type,
            stream=stream,
            alarm_type=alarm_type,
            alarm_id=alarm_id,
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

    def get_network_base_info(
        self,
        *,
        port: int = 80,
        scheme: str = "http",
        auth_code: str | None = None,
        verify_tls: bool | None = None,
        debug: bool = False,
    ) -> CameraDeviceNetworkBaseInfo:
        """Fetch read-only extended network base settings from `/tdkcgi`.

        This mirrors the original app's VSU `get.network.base` request and
        exposes RTSP, HTTP, media ports, transfer policy, DNS, capability
        flags, and LAN interface details when the firmware provides them.

        Args:
            port: Camera CGI HTTP(S) port.
            scheme: URL scheme, usually `"http"` for LAN CGI access.
            auth_code: Optional explicit device auth code. When omitted,
                `Camera(..., auth_code=...)` or `AUTH_CODE` from `.env` is
                used. This method never performs cloud login by itself.
            verify_tls: Override TLS certificate verification for HTTPS CGI.
            debug: Enable debug logging for the raw CGI exchange.

        Returns:
            `CameraDeviceNetworkBaseInfo` with extended network-base fields.
        """

        return fetch_network_base_info(
            self._resolve_local_cgi_endpoint(
                port=port,
                scheme=scheme,
                auth_code=auth_code,
                verify_tls=verify_tls,
                debug=debug,
            )
        )

    def get_network_interfaces(
        self,
        *,
        port: int = 80,
        scheme: str = "http",
        auth_code: str | None = None,
        verify_tls: bool | None = None,
        debug: bool = False,
    ) -> tuple[CameraDeviceLanInfo, ...]:
        """Fetch read-only LAN interface summaries from `/tdkcgi`.

        This is a convenience wrapper around `get_network_info()` that returns
        normalized LAN interfaces. If firmware only returns top-level network
        fields, they are exposed as a single synthetic interface.

        Args:
            port: Camera CGI HTTP(S) port.
            scheme: URL scheme, usually `"http"` for LAN CGI access.
            auth_code: Optional explicit device auth code. When omitted,
                `Camera(..., auth_code=...)` or `AUTH_CODE` from `.env` is
                used. This method never performs cloud login by itself.
            verify_tls: Override TLS certificate verification for HTTPS CGI.
            debug: Enable debug logging for the raw CGI exchange.

        Returns:
            Tuple of LAN interface descriptions.
        """

        return network_interfaces_from_network_info(
            self.get_network_info(
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

    def get_upgrade_version_info(
        self,
        *,
        port: int = 80,
        scheme: str = "http",
        auth_code: str | None = None,
        verify_tls: bool | None = None,
        debug: bool = False,
    ) -> CameraDeviceUpgradeVersionInfo:
        """Fetch read-only latest firmware version from `/tdkcgi`.

        This mirrors the original app's `get.system.upgradeversion` request
        and uses `Camera(..., device_host=...)`.

        Args:
            port: Camera CGI HTTP(S) port.
            scheme: URL scheme, usually `"http"` for LAN CGI access.
            auth_code: Optional explicit device auth code. When omitted,
                `Camera(..., auth_code=...)` or `AUTH_CODE` from `.env` is
                used. This method never performs cloud login by itself.
            verify_tls: Override TLS certificate verification for HTTPS CGI.
            debug: Enable debug logging for the raw CGI exchange.

        Returns:
            `CameraDeviceUpgradeVersionInfo` with latest firmware version and
            release time.
        """

        return fetch_upgrade_version_info(
            self._resolve_local_cgi_endpoint(
                port=port,
                scheme=scheme,
                auth_code=auth_code,
                verify_tls=verify_tls,
                debug=debug,
            )
        )

    def get_upgrade_status_info(
        self,
        *,
        port: int = 80,
        scheme: str = "http",
        auth_code: str | None = None,
        verify_tls: bool | None = None,
        debug: bool = False,
    ) -> CameraDeviceUpgradeStatusInfo:
        """Fetch read-only firmware upgrade status from `/tdkcgi`.

        This mirrors the original app's `get.system.upgradestatus` request
        and uses `Camera(..., device_host=...)`.

        Args:
            port: Camera CGI HTTP(S) port.
            scheme: URL scheme, usually `"http"` for LAN CGI access.
            auth_code: Optional explicit device auth code. When omitted,
                `Camera(..., auth_code=...)` or `AUTH_CODE` from `.env` is
                used. This method never performs cloud login by itself.
            verify_tls: Override TLS certificate verification for HTTPS CGI.
            debug: Enable debug logging for the raw CGI exchange.

        Returns:
            `CameraDeviceUpgradeStatusInfo` with native status code, version,
            and time.
        """

        return fetch_upgrade_status_info(
            self._resolve_local_cgi_endpoint(
                port=port,
                scheme=scheme,
                auth_code=auth_code,
                verify_tls=verify_tls,
                debug=debug,
            )
        )

    def get_upgrade_process_info(
        self,
        *,
        port: int = 80,
        scheme: str = "http",
        auth_code: str | None = None,
        verify_tls: bool | None = None,
        debug: bool = False,
    ) -> CameraDeviceUpgradeProcessInfo:
        """Fetch read-only firmware upgrade progress from `/tdkcgi`.

        This mirrors the original app's `get.system.upgradeprocess` request
        and uses `Camera(..., device_host=...)`.

        Args:
            port: Camera CGI HTTP(S) port.
            scheme: URL scheme, usually `"http"` for LAN CGI access.
            auth_code: Optional explicit device auth code. When omitted,
                `Camera(..., auth_code=...)` or `AUTH_CODE` from `.env` is
                used. This method never performs cloud login by itself.
            verify_tls: Override TLS certificate verification for HTTPS CGI.
            debug: Enable debug logging for the raw CGI exchange.

        Returns:
            `CameraDeviceUpgradeProcessInfo` with native progress value.
        """

        return fetch_upgrade_process_info(
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

    def get_video_channels(
        self,
        *,
        port: int = 80,
        scheme: str = "http",
        auth_code: str | None = None,
        verify_tls: bool | None = None,
        debug: bool = False,
    ) -> tuple[CameraDeviceVideoChannelInfo, ...]:
        """Fetch read-only video channels from `/tdkcgi`.

        This is a convenience wrapper around `get_video_config()`.

        Args:
            port: Camera CGI HTTP(S) port.
            scheme: URL scheme, usually `"http"` for LAN CGI access.
            auth_code: Optional explicit device auth code. When omitted,
                `Camera(..., auth_code=...)` or `AUTH_CODE` from `.env` is
                used. This method never performs cloud login by itself.
            verify_tls: Override TLS certificate verification for HTTPS CGI.
            debug: Enable debug logging for the raw CGI exchange.

        Returns:
            Tuple of video channel descriptions.
        """

        return tuple(
            self.get_video_config(
                port=port,
                scheme=scheme,
                auth_code=auth_code,
                verify_tls=verify_tls,
                debug=debug,
            ).channels
        )

    def get_stream_profiles(
        self,
        *,
        channel_id: str | int | None = None,
        port: int = 80,
        scheme: str = "http",
        auth_code: str | None = None,
        verify_tls: bool | None = None,
        debug: bool = False,
    ) -> tuple[CameraDeviceStreamProfile, ...]:
        """Fetch flattened read-only video stream profiles from `/tdkcgi`.

        This is a convenience wrapper around `get_video_config()` that flattens
        channel stream blocks such as `mainstream` and `substream`.

        Args:
            channel_id: Optional channel id filter.
            port: Camera CGI HTTP(S) port.
            scheme: URL scheme, usually `"http"` for LAN CGI access.
            auth_code: Optional explicit device auth code. When omitted,
                `Camera(..., auth_code=...)` or `AUTH_CODE` from `.env` is
                used. This method never performs cloud login by itself.
            verify_tls: Override TLS certificate verification for HTTPS CGI.
            debug: Enable debug logging for the raw CGI exchange.

        Returns:
            Tuple of flattened stream profiles.
        """

        return stream_profiles_from_video_config(
            self.get_video_config(
                port=port,
                scheme=scheme,
                auth_code=auth_code,
                verify_tls=verify_tls,
                debug=debug,
            ),
            channel_id=str(channel_id) if channel_id is not None else None,
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
