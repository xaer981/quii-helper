"""Camera-facing aliases for read-only device CGI models."""

from dataclasses import dataclass, field

from quii_helper.device.cgi import (
    DeviceAlarmChannel as CameraDeviceAlarmChannel,
)
from quii_helper.device.cgi import (
    DeviceAlarmChannelInfo as CameraDeviceAlarmChannelInfo,
)
from quii_helper.device.cgi import (
    DeviceAlarmInputChannel as CameraDeviceAlarmInputChannel,
)
from quii_helper.device.cgi import (
    DeviceAlarmInputInfo as CameraDeviceAlarmInputInfo,
)
from quii_helper.device.cgi import (
    DeviceAlarmMotionDetectionInfo as CameraDeviceAlarmMotionDetectionInfo,
)
from quii_helper.device.cgi import (
    DeviceAlarmScheduleDay as CameraDeviceAlarmScheduleDay,
)
from quii_helper.device.cgi import (
    DeviceAlarmScheduleInfo as CameraDeviceAlarmScheduleInfo,
)
from quii_helper.device.cgi import (
    DeviceAlarmScheduleSlot as CameraDeviceAlarmScheduleSlot,
)
from quii_helper.device.cgi import (
    DeviceAlarmVideoLostInfo as CameraDeviceAlarmVideoLostInfo,
)
from quii_helper.device.cgi import (
    DeviceAlarmVideoShelterInfo as CameraDeviceAlarmVideoShelterInfo,
)
from quii_helper.device.cgi import (
    DeviceAllInfo as CameraDeviceAllInfo,
)
from quii_helper.device.cgi import (
    DeviceAttachmentAlarm as CameraDeviceAttachmentAlarm,
)
from quii_helper.device.cgi import (
    DeviceAttachmentChannel as CameraDeviceAttachmentChannel,
)
from quii_helper.device.cgi import (
    DeviceAttachmentElevator as CameraDeviceAttachmentElevator,
)
from quii_helper.device.cgi import (
    DeviceAttachmentInfo as CameraDeviceAttachmentInfo,
)
from quii_helper.device.cgi import (
    DeviceAttachmentLock as CameraDeviceAttachmentLock,
)
from quii_helper.device.cgi import (
    DeviceAttachmentProfile as CameraDeviceAttachmentProfile,
)
from quii_helper.device.cgi import (
    DeviceAttachmentSmartSwitch as CameraDeviceAttachmentSmartSwitch,
)
from quii_helper.device.cgi import (
    DeviceCapabilitiesInfo as CameraDeviceCapabilitiesInfo,
)
from quii_helper.device.cgi import (
    DeviceFpsChannelInfo as CameraDeviceFpsChannelInfo,
)
from quii_helper.device.cgi import (
    DeviceFpsInfo as CameraDeviceFpsInfo,
)
from quii_helper.device.cgi import (
    DeviceGeneralInfo as CameraDeviceGeneralInfo,
)
from quii_helper.device.cgi import (
    DeviceHumanTraceInfo as CameraDeviceHumanTraceInfo,
)
from quii_helper.device.cgi import (
    DeviceLanInfo as CameraDeviceLanInfo,
)
from quii_helper.device.cgi import (
    DeviceMotionDetectionInfo as CameraDeviceMotionDetectionInfo,
)
from quii_helper.device.cgi import (
    DeviceMoveDetectionInfo as CameraDeviceMoveDetectionInfo,
)
from quii_helper.device.cgi import (
    DeviceNetworkBaseAbility as CameraDeviceNetworkBaseAbility,
)
from quii_helper.device.cgi import (
    DeviceNetworkBaseInfo as CameraDeviceNetworkBaseInfo,
)
from quii_helper.device.cgi import (
    DeviceNetworkInfo as CameraDeviceNetworkInfo,
)
from quii_helper.device.cgi import (
    DeviceNetworkTransferPolicy as CameraDeviceNetworkTransferPolicy,
)
from quii_helper.device.cgi import (
    DeviceProductInfo as CameraDeviceProductInfo,
)
from quii_helper.device.cgi import (
    DevicePtzPreset as CameraDevicePtzPreset,
)
from quii_helper.device.cgi import (
    DevicePtzPresetInfo as CameraDevicePtzPresetInfo,
)
from quii_helper.device.cgi import (
    DevicePtzStateInfo as CameraDevicePtzStateInfo,
)
from quii_helper.device.cgi import (
    DeviceQrCodeInfo as CameraDeviceQrCodeInfo,
)
from quii_helper.device.cgi import (
    DeviceRecordAlarmInfo as CameraDeviceRecordAlarmInfo,
)
from quii_helper.device.cgi import (
    DeviceRecordConfigInfo as CameraDeviceRecordConfigInfo,
)
from quii_helper.device.cgi import (
    DeviceRecordFileInfo as CameraDeviceRecordFileInfo,
)
from quii_helper.device.cgi import (
    DeviceRecordListInfo as CameraDeviceRecordListInfo,
)
from quii_helper.device.cgi import (
    DeviceRecordMessageInfo as CameraDeviceRecordMessageInfo,
)
from quii_helper.device.cgi import (
    DeviceRecordScheduleTime as CameraDeviceRecordScheduleTime,
)
from quii_helper.device.cgi import (
    DeviceRecordSessionInfo as CameraDeviceRecordSessionInfo,
)
from quii_helper.device.cgi import (
    DeviceScreenFlipInfo as CameraDeviceScreenFlipInfo,
)
from quii_helper.device.cgi import (
    DeviceSmartLightInfo as CameraDeviceSmartLightInfo,
)
from quii_helper.device.cgi import (
    DeviceSmartLightItem as CameraDeviceSmartLightItem,
)
from quii_helper.device.cgi import (
    DeviceSoundLightChannelInfo as CameraDeviceSoundLightChannelInfo,
)
from quii_helper.device.cgi import (
    DeviceSoundLightInfo as CameraDeviceSoundLightInfo,
)
from quii_helper.device.cgi import (
    DeviceStorageDisk as CameraDeviceStorageDisk,
)
from quii_helper.device.cgi import (
    DeviceStorageInfo as CameraDeviceStorageInfo,
)
from quii_helper.device.cgi import (
    DeviceStreamKeyInfo as CameraDeviceStreamKeyInfo,
)
from quii_helper.device.cgi import (
    DeviceTfCardDiskInfo as CameraDeviceTfCardDiskInfo,
)
from quii_helper.device.cgi import (
    DeviceTfCardInfo as CameraDeviceTfCardInfo,
)
from quii_helper.device.cgi import (
    DeviceTimeInfo as CameraDeviceTimeInfo,
)
from quii_helper.device.cgi import (
    DeviceTimeTitleInfo as CameraDeviceTimeTitleInfo,
)
from quii_helper.device.cgi import (
    DeviceTimeTitleOverlay as CameraDeviceTimeTitleOverlay,
)
from quii_helper.device.cgi import (
    DeviceUpgradeProcessInfo as CameraDeviceUpgradeProcessInfo,
)
from quii_helper.device.cgi import (
    DeviceUpgradeStatusInfo as CameraDeviceUpgradeStatusInfo,
)
from quii_helper.device.cgi import (
    DeviceUpgradeVersionInfo as CameraDeviceUpgradeVersionInfo,
)
from quii_helper.device.cgi import (
    DeviceVideoChannelInfo as CameraDeviceVideoChannelInfo,
)
from quii_helper.device.cgi import (
    DeviceVideoConfigInfo as CameraDeviceVideoConfigInfo,
)
from quii_helper.device.cgi import (
    DeviceVideoStreamInfo as CameraDeviceVideoStreamInfo,
)
from quii_helper.device.cgi import (
    DeviceVideoSwitchInfo as CameraDeviceVideoSwitchInfo,
)
from quii_helper.device.cgi import (
    DeviceWifiListInfo as CameraDeviceWifiListInfo,
)
from quii_helper.device.cgi import (
    DeviceWifiNetwork as CameraDeviceWifiNetwork,
)

CameraDeviceProfileResponse = (
    CameraDeviceAllInfo
    | CameraDeviceCapabilitiesInfo
    | CameraDeviceFpsInfo
    | CameraDeviceGeneralInfo
    | CameraDeviceAlarmInputInfo
    | CameraDeviceAlarmMotionDetectionInfo
    | CameraDeviceAlarmScheduleInfo
    | CameraDeviceAlarmVideoLostInfo
    | CameraDeviceAlarmVideoShelterInfo
    | CameraDeviceMotionDetectionInfo
    | CameraDeviceNetworkBaseInfo
    | CameraDeviceNetworkInfo
    | CameraDeviceProductInfo
    | CameraDeviceQrCodeInfo
    | CameraDevicePtzPresetInfo
    | CameraDevicePtzStateInfo
    | CameraDeviceScreenFlipInfo
    | CameraDeviceSmartLightInfo
    | CameraDeviceStorageInfo
    | CameraDeviceTfCardInfo
    | CameraDeviceTimeInfo
    | CameraDeviceTimeTitleInfo
    | CameraDeviceUpgradeProcessInfo
    | CameraDeviceUpgradeStatusInfo
    | CameraDeviceUpgradeVersionInfo
    | CameraDeviceVideoConfigInfo
    | CameraDeviceVideoSwitchInfo
    | CameraDeviceWifiListInfo
)


@dataclass(frozen=True)
class CameraDeviceStreamProfile:
    """Flattened read-only stream profile.

    This combines channel metadata from `get.encode` with one concrete stream
    block such as `mainstream` or `substream`.
    """

    channel_id: str
    channel_name: str
    stream_name: str
    enabled: bool | None = None
    compression: str = ""
    resolution: str = ""
    bitrate: int | None = None
    bitrate_control: str = ""
    fps: int | None = None
    gop: int | None = None
    quality: int | None = None
    audio_enabled: bool | None = None
    h264plus_enabled: bool | None = None
    raw: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class CameraDeviceCommandStatus:
    """Status of one read-only `/tdkcgi` command in a device profile.

    Attributes:
        command: Original `/tdkcgi` command name.
        error: Numeric device error code.
        ok: Whether the device returned `error=0`.
        unsupported: Whether the response looks like a firmware-level
            unsupported/rejected command (`error=-1` with empty content).
        empty_content: Whether `body/content` was empty.
    """

    command: str
    error: int
    ok: bool
    unsupported: bool
    empty_content: bool


@dataclass(frozen=True)
class CameraDeviceProfile:
    """Aggregated read-only local CGI profile for a camera.

    The profile keeps every individual typed response and adds command-level
    status lists so callers can distinguish supported, unsupported, and failed
    firmware commands without manually inspecting `error` fields.
    """

    all_info: CameraDeviceAllInfo
    product: CameraDeviceProductInfo
    time: CameraDeviceTimeInfo
    storage: CameraDeviceStorageInfo
    network: CameraDeviceNetworkInfo
    general: CameraDeviceGeneralInfo
    capabilities: CameraDeviceCapabilitiesInfo
    video_config: CameraDeviceVideoConfigInfo
    wifi: CameraDeviceWifiListInfo
    screen_flip: CameraDeviceScreenFlipInfo
    video_switch: CameraDeviceVideoSwitchInfo
    time_title: CameraDeviceTimeTitleInfo
    command_statuses: tuple[CameraDeviceCommandStatus, ...] = field(
        default_factory=tuple
    )

    @property
    def model(self) -> str:
        """Best available device model from product or broad status data."""

        return self.product.model or self.all_info.model

    @property
    def firmware_version(self) -> str:
        """Best available firmware version from product or broad status data."""

        return (
            self.product.version
            or self.all_info.version
            or self.all_info.latest_version
        )

    @property
    def mac(self) -> str:
        """Best available MAC address from product or broad status data."""

        return self.product.mac or self.all_info.mac

    @property
    def time_zone(self) -> str:
        """Best available device time zone."""

        return self.time.time_zone or self.all_info.time_zone

    @property
    def supported_commands(self) -> tuple[str, ...]:
        """Commands that returned `error=0`."""

        return tuple(
            status.command for status in self.command_statuses if status.ok
        )

    @property
    def unsupported_commands(self) -> tuple[str, ...]:
        """Commands rejected by firmware with `error=-1` and empty content."""

        return tuple(
            status.command
            for status in self.command_statuses
            if status.unsupported
        )

    @property
    def failed_commands(self) -> tuple[str, ...]:
        """Commands that failed but do not look like unsupported commands."""

        return tuple(
            status.command
            for status in self.command_statuses
            if not status.ok and not status.unsupported
        )

    @property
    def status_by_command(self) -> dict[str, CameraDeviceCommandStatus]:
        """Command statuses indexed by command name."""

        return {status.command: status for status in self.command_statuses}

    @property
    def video_channels(self) -> tuple[CameraDeviceVideoChannelInfo, ...]:
        """Video channels reported by `get.encode`."""

        return tuple(self.video_config.channels)

    @property
    def stream_profiles(self) -> tuple[CameraDeviceStreamProfile, ...]:
        """Flattened stream profiles reported by `get.encode`."""

        return stream_profiles_from_video_config(self.video_config)

    @property
    def network_interfaces(self) -> tuple[CameraDeviceLanInfo, ...]:
        """LAN interfaces reported by `get.network.config`."""

        return network_interfaces_from_network_info(self.network)


def stream_profiles_from_video_config(
    video_config: CameraDeviceVideoConfigInfo,
    *,
    channel_id: str | None = None,
) -> tuple[CameraDeviceStreamProfile, ...]:
    """Flatten `get.encode` channel/stream data into stream profiles."""

    profiles: list[CameraDeviceStreamProfile] = []
    for channel in video_config.channels:
        if channel_id is not None and channel.channel_id != str(channel_id):
            continue
        for stream in channel.streams:
            profiles.append(
                CameraDeviceStreamProfile(
                    channel_id=channel.channel_id,
                    channel_name=channel.name,
                    stream_name=stream.name,
                    enabled=stream.enabled,
                    compression=stream.compression,
                    resolution=stream.resolution,
                    bitrate=stream.bitrate,
                    bitrate_control=stream.bitrate_control,
                    fps=stream.fps,
                    gop=stream.gop,
                    quality=stream.quality,
                    audio_enabled=stream.audio_enabled,
                    h264plus_enabled=stream.h264plus_enabled,
                    raw=stream.raw,
                )
            )
    return tuple(profiles)


def network_interfaces_from_network_info(
    network_info: CameraDeviceNetworkInfo,
) -> tuple[CameraDeviceLanInfo, ...]:
    """Return LAN interfaces, falling back to top-level network fields."""

    if network_info.lan_interfaces:
        return tuple(network_info.lan_interfaces)
    if not any(
        (
            network_info.address,
            network_info.subnet_mask,
            network_info.gateway,
            network_info.dhcp is not None,
        )
    ):
        return ()
    return (
        CameraDeviceLanInfo(
            ip_address=network_info.address,
            subnet_mask=network_info.subnet_mask,
            gateway=network_info.gateway,
            dhcp=network_info.dhcp,
        ),
    )


def command_status_for_response(
    command: str,
    response: CameraDeviceProfileResponse,
) -> CameraDeviceCommandStatus:
    """Build a command status from a typed read-only CGI response."""

    raw = response.raw
    empty_content = raw is not None and not raw.content
    return CameraDeviceCommandStatus(
        command=command,
        error=response.error,
        ok=response.error == 0,
        unsupported=response.error == -1 and empty_content,
        empty_content=empty_content,
    )


__all__ = [
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
    "CameraDeviceAttachmentAlarm",
    "CameraDeviceAttachmentChannel",
    "CameraDeviceAttachmentElevator",
    "CameraDeviceAttachmentInfo",
    "CameraDeviceAttachmentLock",
    "CameraDeviceAttachmentProfile",
    "CameraDeviceAttachmentSmartSwitch",
    "CameraDeviceCapabilitiesInfo",
    "CameraDeviceCommandStatus",
    "CameraDeviceFpsChannelInfo",
    "CameraDeviceFpsInfo",
    "CameraDeviceGeneralInfo",
    "CameraDeviceHumanTraceInfo",
    "CameraDeviceLanInfo",
    "CameraDeviceMoveDetectionInfo",
    "CameraDeviceMotionDetectionInfo",
    "CameraDeviceNetworkBaseAbility",
    "CameraDeviceNetworkBaseInfo",
    "CameraDeviceNetworkInfo",
    "CameraDeviceNetworkTransferPolicy",
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
    "CameraDeviceProfileResponse",
    "CameraDeviceScreenFlipInfo",
    "CameraDeviceSmartLightInfo",
    "CameraDeviceSmartLightItem",
    "CameraDeviceSoundLightChannelInfo",
    "CameraDeviceSoundLightInfo",
    "CameraDeviceStorageDisk",
    "CameraDeviceStorageInfo",
    "CameraDeviceStreamKeyInfo",
    "CameraDeviceTfCardDiskInfo",
    "CameraDeviceTfCardInfo",
    "CameraDeviceStreamProfile",
    "CameraDeviceTimeInfo",
    "CameraDeviceTimeTitleInfo",
    "CameraDeviceTimeTitleOverlay",
    "CameraDeviceUpgradeProcessInfo",
    "CameraDeviceUpgradeStatusInfo",
    "CameraDeviceUpgradeVersionInfo",
    "CameraDeviceVideoChannelInfo",
    "CameraDeviceVideoConfigInfo",
    "CameraDeviceVideoStreamInfo",
    "CameraDeviceVideoSwitchInfo",
    "CameraDeviceWifiListInfo",
    "CameraDeviceWifiNetwork",
    "command_status_for_response",
    "network_interfaces_from_network_info",
    "stream_profiles_from_video_config",
]
