from typing import Any

import pytest

from quii_helper.camera import (
    Camera,
    CameraDeviceAlarmChannelInfo,
    CameraDeviceAlarmInputInfo,
    CameraDeviceAlarmMotionDetectionInfo,
    CameraDeviceAlarmScheduleInfo,
    CameraDeviceAlarmVideoLostInfo,
    CameraDeviceAlarmVideoShelterInfo,
    CameraDeviceAllInfo,
    CameraDeviceAttachmentInfo,
    CameraDeviceCapabilitiesInfo,
    CameraDeviceFpsInfo,
    CameraDeviceGeneralInfo,
    CameraDeviceHumanTraceInfo,
    CameraDeviceLanInfo,
    CameraDeviceMotionDetectionInfo,
    CameraDeviceMoveDetectionInfo,
    CameraDeviceNetworkBaseInfo,
    CameraDeviceNetworkInfo,
    CameraDeviceProductInfo,
    CameraDeviceProfile,
    CameraDevicePtzPresetInfo,
    CameraDevicePtzStateInfo,
    CameraDeviceQrCodeInfo,
    CameraDeviceRecordAlarmInfo,
    CameraDeviceRecordConfigInfo,
    CameraDeviceRecordFileInfo,
    CameraDeviceRecordListInfo,
    CameraDeviceRecordMessageInfo,
    CameraDeviceRecordSessionInfo,
    CameraDeviceScreenFlipInfo,
    CameraDeviceSmartLightInfo,
    CameraDeviceSoundLightInfo,
    CameraDeviceStorageInfo,
    CameraDeviceStreamKeyInfo,
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
)
from quii_helper.camera import api as camera_api
from quii_helper.camera.device_cgi import (
    CameraDeviceVideoStreamInfo,
    DeviceCgiEndpoint,
)
from quii_helper.camera.device_cgi import service as device_cgi_service
from quii_helper.camera.device_cgi.models import (
    CameraDeviceCommandStatus,
    CameraDeviceProfileResponse,
    command_status_for_response,
)
from quii_helper.config import AutonomousConfig
from quii_helper.device.cgi import DeviceCgiResponse
from quii_helper.support.errors import ConfigurationError


def _config(
    *, device_host: str = "192.0.2.10", auth_code: str = "config-auth-code"
) -> AutonomousConfig:
    return AutonomousConfig(
        device_id="device",
        device_host=device_host,
        auth_code=auth_code,
        cloud_account="account",
        cloud_password="password",
        service_url="https://service.example",
        auth_url="https://auth.example",
        oem="OEM",
        app_id=1,
        client_type=2,
        client_id="client-id",
        ip_region_id=3,
        tls_verify=False,
    )


class CameraDeviceCgiTests:
    def test_storage_info_uses_explicit_endpoint_without_preview(
        self, monkeypatch
    ) -> None:
        camera = Camera(config=_config())
        calls = []

        def fake_fetch_storage_info(
            endpoint: DeviceCgiEndpoint,
        ) -> CameraDeviceStorageInfo:
            calls.append(endpoint)
            return CameraDeviceStorageInfo(
                error=0,
                total_sum=1024,
                free_sum=256,
            )

        monkeypatch.setattr(
            camera_api,
            "fetch_storage_info",
            fake_fetch_storage_info,
        )

        info = camera.get_storage_info(
            port=8080,
            auth_code="auth-code",
            debug=True,
        )

        assert 1024 == info.total_sum
        assert [
            DeviceCgiEndpoint(
                host="192.0.2.10",
                port=8080,
                scheme="http",
                auth_code="auth-code",
                verify_tls=False,
                debug=True,
            )
        ] == calls

    def test_tf_card_info_uses_explicit_endpoint_without_preview(
        self, monkeypatch
    ) -> None:
        camera = Camera(config=_config())
        calls = []

        def fake_fetch_tf_card_info(
            endpoint: DeviceCgiEndpoint,
        ) -> CameraDeviceTfCardInfo:
            calls.append(endpoint)
            return CameraDeviceTfCardInfo(
                error=0,
                total_sum=1024,
                free_sum=256,
            )

        monkeypatch.setattr(
            camera_api,
            "fetch_tf_card_info",
            fake_fetch_tf_card_info,
        )

        info = camera.get_tf_card_info(
            port=8080,
            auth_code="auth-code",
            debug=True,
        )

        assert 1024 == info.total_sum
        assert [
            DeviceCgiEndpoint(
                host="192.0.2.10",
                port=8080,
                scheme="http",
                auth_code="auth-code",
                verify_tls=False,
                debug=True,
            )
        ] == calls

    def test_device_attachment_info_uses_same_endpoint_resolver(
        self, monkeypatch
    ) -> None:
        camera = Camera(config=_config())
        calls = []

        def fake_fetch_device_attachment_info(
            endpoint: DeviceCgiEndpoint,
        ) -> CameraDeviceAttachmentInfo:
            calls.append(endpoint)
            return CameraDeviceAttachmentInfo(error=0)

        monkeypatch.setattr(
            camera_api,
            "fetch_device_attachment_info",
            fake_fetch_device_attachment_info,
        )

        info = camera.get_device_attachment_info(
            port=8080,
            auth_code="auth-code",
            debug=True,
        )

        assert 0 == info.error
        assert [
            DeviceCgiEndpoint(
                host="192.0.2.10",
                port=8080,
                scheme="http",
                auth_code="auth-code",
                verify_tls=False,
                debug=True,
            )
        ] == calls

    def test_motion_detection_info_uses_same_endpoint_resolver(
        self, monkeypatch
    ) -> None:
        camera = Camera(config=_config())
        calls = []

        def fake_fetch_motion_detection_info(
            endpoint: DeviceCgiEndpoint,
        ) -> CameraDeviceMotionDetectionInfo:
            calls.append(endpoint)
            return CameraDeviceMotionDetectionInfo(
                error=0,
                channel_id=1,
                enabled=True,
                sensitivity=4,
            )

        monkeypatch.setattr(
            camera_api,
            "fetch_motion_detection_info",
            fake_fetch_motion_detection_info,
        )

        info = camera.get_motion_detection_info(
            port=8080,
            auth_code="auth-code",
            debug=True,
        )

        assert info.enabled is True
        assert 4 == info.sensitivity
        assert [
            DeviceCgiEndpoint(
                host="192.0.2.10",
                port=8080,
                scheme="http",
                auth_code="auth-code",
                verify_tls=False,
                debug=True,
            )
        ] == calls

    def test_alarm_motion_detection_info_uses_same_endpoint_resolver(
        self, monkeypatch
    ) -> None:
        camera = Camera(config=_config())
        calls = []

        def fake_fetch_alarm_motion_detection_info(
            endpoint: DeviceCgiEndpoint,
            *,
            channel_id: int = 1,
        ) -> CameraDeviceAlarmMotionDetectionInfo:
            calls.append((endpoint, channel_id))
            return CameraDeviceAlarmMotionDetectionInfo(
                error=0,
                channel_id=channel_id,
                enabled=True,
                sensitivity=5,
                peds_enabled=1,
            )

        monkeypatch.setattr(
            camera_api,
            "fetch_alarm_motion_detection_info",
            fake_fetch_alarm_motion_detection_info,
        )

        info = camera.get_alarm_motion_detection_info(
            channel_id=2,
            port=8080,
            auth_code="auth-code",
            debug=True,
        )

        assert info.enabled is True
        assert 2 == info.channel_id
        assert [
            (
                DeviceCgiEndpoint(
                    host="192.0.2.10",
                    port=8080,
                    scheme="http",
                    auth_code="auth-code",
                    verify_tls=False,
                    debug=True,
                ),
                2,
            )
        ] == calls

    def test_alarm_input_info_uses_same_endpoint_resolver(
        self, monkeypatch
    ) -> None:
        camera = Camera(config=_config())
        calls = []

        def fake_fetch_alarm_input_info(
            endpoint: DeviceCgiEndpoint,
            *,
            channel_id: int = -1,
        ) -> CameraDeviceAlarmInputInfo:
            calls.append((endpoint, channel_id))
            return CameraDeviceAlarmInputInfo(error=0)

        monkeypatch.setattr(
            camera_api,
            "fetch_alarm_input_info",
            fake_fetch_alarm_input_info,
        )

        info = camera.get_alarm_input_info(
            channel_id=2,
            port=8080,
            auth_code="auth-code",
            debug=True,
        )

        assert 0 == info.error
        assert [
            (
                DeviceCgiEndpoint(
                    host="192.0.2.10",
                    port=8080,
                    scheme="http",
                    auth_code="auth-code",
                    verify_tls=False,
                    debug=True,
                ),
                2,
            )
        ] == calls

    def test_alarm_video_lost_info_uses_same_endpoint_resolver(
        self, monkeypatch
    ) -> None:
        camera = Camera(config=_config())
        calls = []

        def fake_fetch_alarm_video_lost_info(
            endpoint: DeviceCgiEndpoint,
            *,
            channel_id: int = 1,
        ) -> CameraDeviceAlarmVideoLostInfo:
            calls.append((endpoint, channel_id))
            return CameraDeviceAlarmVideoLostInfo(
                error=0,
                channel_id=channel_id,
                enabled=True,
            )

        monkeypatch.setattr(
            camera_api,
            "fetch_alarm_video_lost_info",
            fake_fetch_alarm_video_lost_info,
        )

        info = camera.get_alarm_video_lost_info(
            channel_id=2,
            port=8080,
            auth_code="auth-code",
            debug=True,
        )

        assert info.enabled is True
        assert [
            (
                DeviceCgiEndpoint(
                    host="192.0.2.10",
                    port=8080,
                    scheme="http",
                    auth_code="auth-code",
                    verify_tls=False,
                    debug=True,
                ),
                2,
            )
        ] == calls

    def test_alarm_video_shelter_info_uses_same_endpoint_resolver(
        self, monkeypatch
    ) -> None:
        camera = Camera(config=_config())
        calls = []

        def fake_fetch_alarm_video_shelter_info(
            endpoint: DeviceCgiEndpoint,
            *,
            channel_id: int = 1,
        ) -> CameraDeviceAlarmVideoShelterInfo:
            calls.append((endpoint, channel_id))
            return CameraDeviceAlarmVideoShelterInfo(
                error=0,
                channel_id=channel_id,
                enabled=True,
                sensitivity=4,
            )

        monkeypatch.setattr(
            camera_api,
            "fetch_alarm_video_shelter_info",
            fake_fetch_alarm_video_shelter_info,
        )

        info = camera.get_alarm_video_shelter_info(
            channel_id=2,
            port=8080,
            auth_code="auth-code",
            debug=True,
        )

        assert 4 == info.sensitivity
        assert [
            (
                DeviceCgiEndpoint(
                    host="192.0.2.10",
                    port=8080,
                    scheme="http",
                    auth_code="auth-code",
                    verify_tls=False,
                    debug=True,
                ),
                2,
            )
        ] == calls

    def test_alarm_schedule_methods_use_same_endpoint_resolver(
        self,
        monkeypatch,
    ) -> None:
        camera = Camera(config=_config())
        calls = []

        def fake_fetch_alarm_motion_detection_schedule_info(
            endpoint: DeviceCgiEndpoint,
            *,
            channel_id: int = 1,
        ) -> CameraDeviceAlarmScheduleInfo:
            calls.append(("motion", endpoint, channel_id))
            return CameraDeviceAlarmScheduleInfo(
                error=0,
                alarm_type="motiondetection",
                channel_id=channel_id,
            )

        def fake_fetch_alarm_video_lost_schedule_info(
            endpoint: DeviceCgiEndpoint,
            *,
            channel_id: int = 1,
        ) -> CameraDeviceAlarmScheduleInfo:
            calls.append(("video-lost", endpoint, channel_id))
            return CameraDeviceAlarmScheduleInfo(
                error=0,
                alarm_type="videolost",
                channel_id=channel_id,
            )

        def fake_fetch_alarm_video_shelter_schedule_info(
            endpoint: DeviceCgiEndpoint,
            *,
            channel_id: int = 1,
        ) -> CameraDeviceAlarmScheduleInfo:
            calls.append(("video-shelter", endpoint, channel_id))
            return CameraDeviceAlarmScheduleInfo(
                error=0,
                alarm_type="videoshelter",
                channel_id=channel_id,
            )

        def fake_fetch_alarm_input_schedule_info(
            endpoint: DeviceCgiEndpoint,
            *,
            channel_id: int = 1,
        ) -> CameraDeviceAlarmScheduleInfo:
            calls.append(("alarm-input", endpoint, channel_id))
            return CameraDeviceAlarmScheduleInfo(
                error=0,
                alarm_type="alarmin",
                channel_id=channel_id,
            )

        monkeypatch.setattr(
            camera_api,
            "fetch_alarm_motion_detection_schedule_info",
            fake_fetch_alarm_motion_detection_schedule_info,
        )
        monkeypatch.setattr(
            camera_api,
            "fetch_alarm_video_lost_schedule_info",
            fake_fetch_alarm_video_lost_schedule_info,
        )
        monkeypatch.setattr(
            camera_api,
            "fetch_alarm_video_shelter_schedule_info",
            fake_fetch_alarm_video_shelter_schedule_info,
        )
        monkeypatch.setattr(
            camera_api,
            "fetch_alarm_input_schedule_info",
            fake_fetch_alarm_input_schedule_info,
        )

        assert (
            "motiondetection"
            == camera.get_alarm_motion_detection_schedule(
                channel_id=2,
                port=8080,
                auth_code="auth-code",
                debug=True,
            ).alarm_type
        )
        assert (
            "videolost"
            == camera.get_alarm_video_lost_schedule(
                channel_id=2,
                port=8080,
                auth_code="auth-code",
                debug=True,
            ).alarm_type
        )
        assert (
            "videoshelter"
            == camera.get_alarm_video_shelter_schedule(
                channel_id=2,
                port=8080,
                auth_code="auth-code",
                debug=True,
            ).alarm_type
        )
        assert (
            "alarmin"
            == camera.get_alarm_input_schedule(
                channel_id=2,
                port=8080,
                auth_code="auth-code",
                debug=True,
            ).alarm_type
        )

        expected_endpoint = DeviceCgiEndpoint(
            host="192.0.2.10",
            port=8080,
            scheme="http",
            auth_code="auth-code",
            verify_tls=False,
            debug=True,
        )
        assert [
            ("motion", expected_endpoint, 2),
            ("video-lost", expected_endpoint, 2),
            ("video-shelter", expected_endpoint, 2),
            ("alarm-input", expected_endpoint, 2),
        ] == calls

    def test_human_trace_info_uses_same_endpoint_resolver(
        self,
        monkeypatch,
    ) -> None:
        camera = Camera(config=_config())
        calls = []

        def fake_fetch_human_trace_info(
            endpoint: DeviceCgiEndpoint,
        ) -> CameraDeviceHumanTraceInfo:
            calls.append(endpoint)
            return CameraDeviceHumanTraceInfo(error=0, enabled=True)

        monkeypatch.setattr(
            camera_api,
            "fetch_human_trace_info",
            fake_fetch_human_trace_info,
        )

        info = camera.get_human_trace_info(
            port=8080,
            auth_code="auth-code",
            debug=True,
        )

        assert info.enabled is True
        assert [
            DeviceCgiEndpoint(
                host="192.0.2.10",
                port=8080,
                scheme="http",
                auth_code="auth-code",
                verify_tls=False,
                debug=True,
            )
        ] == calls

    def test_move_detection_info_uses_same_endpoint_resolver(
        self,
        monkeypatch,
    ) -> None:
        camera = Camera(config=_config())
        calls = []

        def fake_fetch_move_detection_info(
            endpoint: DeviceCgiEndpoint,
        ) -> CameraDeviceMoveDetectionInfo:
            calls.append(endpoint)
            return CameraDeviceMoveDetectionInfo(error=0, enabled=False)

        monkeypatch.setattr(
            camera_api,
            "fetch_move_detection_info",
            fake_fetch_move_detection_info,
        )

        info = camera.get_move_detection_info(
            port=8080,
            auth_code="auth-code",
            debug=True,
        )

        assert info.enabled is False
        assert [
            DeviceCgiEndpoint(
                host="192.0.2.10",
                port=8080,
                scheme="http",
                auth_code="auth-code",
                verify_tls=False,
                debug=True,
            )
        ] == calls

    def test_fps_info_uses_same_endpoint_resolver(self, monkeypatch) -> None:
        camera = Camera(config=_config())
        calls = []

        def fake_fetch_fps_info(
            endpoint: DeviceCgiEndpoint,
            *,
            channel_id: int = -1,
            stream_id: int = -1,
        ) -> CameraDeviceFpsInfo:
            calls.append((endpoint, channel_id, stream_id))
            return CameraDeviceFpsInfo(error=0)

        monkeypatch.setattr(
            camera_api,
            "fetch_fps_info",
            fake_fetch_fps_info,
        )

        info = camera.get_fps_info(
            channel_id=1,
            stream_id=0,
            port=8080,
            auth_code="auth-code",
            debug=True,
        )

        assert 0 == info.error
        assert [
            (
                DeviceCgiEndpoint(
                    host="192.0.2.10",
                    port=8080,
                    scheme="http",
                    auth_code="auth-code",
                    verify_tls=False,
                    debug=True,
                ),
                1,
                0,
            )
        ] == calls

    def test_ptz_info_uses_same_endpoint_resolver(
        self,
        monkeypatch,
    ) -> None:
        camera = Camera(config=_config())
        calls = []

        def fake_fetch_ptz_state_info(
            endpoint: DeviceCgiEndpoint,
        ) -> CameraDevicePtzStateInfo:
            calls.append(("state", endpoint))
            return CameraDevicePtzStateInfo(error=0, position_x=25)

        def fake_fetch_ptz_preset_info(
            endpoint: DeviceCgiEndpoint,
        ) -> CameraDevicePtzPresetInfo:
            calls.append(("presets", endpoint))
            return CameraDevicePtzPresetInfo(error=0)

        monkeypatch.setattr(
            camera_api,
            "fetch_ptz_state_info",
            fake_fetch_ptz_state_info,
        )
        monkeypatch.setattr(
            camera_api,
            "fetch_ptz_preset_info",
            fake_fetch_ptz_preset_info,
        )

        assert (
            25
            == camera.get_ptz_state(
                port=8080,
                auth_code="auth-code",
            ).position_x
        )
        assert (
            0
            == camera.get_ptz_presets(
                port=8080,
                auth_code="auth-code",
            ).error
        )

        expected_endpoint = DeviceCgiEndpoint(
            host="192.0.2.10",
            port=8080,
            scheme="http",
            auth_code="auth-code",
            verify_tls=False,
            debug=False,
        )
        assert [
            ("state", expected_endpoint),
            ("presets", expected_endpoint),
        ] == calls

    def test_upgrade_info_uses_same_endpoint_resolver(
        self,
        monkeypatch,
    ) -> None:
        camera = Camera(config=_config())
        calls = []

        def fake_fetch_upgrade_version_info(
            endpoint: DeviceCgiEndpoint,
        ) -> CameraDeviceUpgradeVersionInfo:
            calls.append(("version", endpoint))
            return CameraDeviceUpgradeVersionInfo(
                error=0,
                version="V401R001B008",
            )

        def fake_fetch_upgrade_status_info(
            endpoint: DeviceCgiEndpoint,
        ) -> CameraDeviceUpgradeStatusInfo:
            calls.append(("status", endpoint))
            return CameraDeviceUpgradeStatusInfo(error=0, status=4)

        def fake_fetch_upgrade_process_info(
            endpoint: DeviceCgiEndpoint,
        ) -> CameraDeviceUpgradeProcessInfo:
            calls.append(("process", endpoint))
            return CameraDeviceUpgradeProcessInfo(error=0, process=37)

        monkeypatch.setattr(
            camera_api,
            "fetch_upgrade_version_info",
            fake_fetch_upgrade_version_info,
        )
        monkeypatch.setattr(
            camera_api,
            "fetch_upgrade_status_info",
            fake_fetch_upgrade_status_info,
        )
        monkeypatch.setattr(
            camera_api,
            "fetch_upgrade_process_info",
            fake_fetch_upgrade_process_info,
        )

        assert (
            "V401R001B008"
            == camera.get_upgrade_version_info(
                port=8080,
                auth_code="auth-code",
            ).version
        )
        assert (
            4
            == camera.get_upgrade_status_info(
                port=8080,
                auth_code="auth-code",
            ).status
        )
        assert (
            37
            == camera.get_upgrade_process_info(
                port=8080,
                auth_code="auth-code",
            ).process
        )

        expected_endpoint = DeviceCgiEndpoint(
            host="192.0.2.10",
            port=8080,
            scheme="http",
            auth_code="auth-code",
            verify_tls=False,
            debug=False,
        )
        assert [
            ("version", expected_endpoint),
            ("status", expected_endpoint),
            ("process", expected_endpoint),
        ] == calls

    def test_smart_light_info_uses_same_endpoint_resolver(
        self,
        monkeypatch,
    ) -> None:
        camera = Camera(config=_config())
        calls = []

        def fake_fetch_smart_light_info(
            endpoint: DeviceCgiEndpoint,
            *,
            room: int = 1,
        ) -> CameraDeviceSmartLightInfo:
            calls.append((endpoint, room))
            return CameraDeviceSmartLightInfo(error=0, room=room, light_num=0)

        monkeypatch.setattr(
            camera_api,
            "fetch_smart_light_info",
            fake_fetch_smart_light_info,
        )

        info = camera.get_smart_light_info(
            room=2,
            port=8080,
            auth_code="auth-code",
            debug=True,
        )

        assert 2 == info.room
        assert [
            (
                DeviceCgiEndpoint(
                    host="192.0.2.10",
                    port=8080,
                    scheme="http",
                    auth_code="auth-code",
                    verify_tls=False,
                    debug=True,
                ),
                2,
            )
        ] == calls

    def test_sound_light_info_uses_same_endpoint_resolver(
        self,
        monkeypatch,
    ) -> None:
        camera = Camera(config=_config())
        calls = []

        def fake_fetch_sound_light_info(
            endpoint: DeviceCgiEndpoint,
            *,
            channel_id: int = 1,
        ) -> CameraDeviceSoundLightInfo:
            calls.append((endpoint, channel_id))
            return CameraDeviceSoundLightInfo(error=0)

        monkeypatch.setattr(
            camera_api,
            "fetch_sound_light_info",
            fake_fetch_sound_light_info,
        )

        info = camera.get_sound_light_info(
            channel_id=1,
            port=8080,
            auth_code="auth-code",
            debug=True,
        )

        assert 0 == info.error
        assert [
            (
                DeviceCgiEndpoint(
                    host="192.0.2.10",
                    port=8080,
                    scheme="http",
                    auth_code="auth-code",
                    verify_tls=False,
                    debug=True,
                ),
                1,
            )
        ] == calls

    def test_video_config_uses_same_endpoint_resolver(
        self, monkeypatch
    ) -> None:
        camera = Camera(config=_config())
        calls = []

        def fake_fetch_video_config_info(
            endpoint: DeviceCgiEndpoint,
        ) -> CameraDeviceVideoConfigInfo:
            calls.append(endpoint)
            return CameraDeviceVideoConfigInfo(error=0)

        monkeypatch.setattr(
            camera_api,
            "fetch_video_config_info",
            fake_fetch_video_config_info,
        )

        info = camera.get_video_config(
            port=8080,
            auth_code="auth-code",
            debug=True,
        )

        assert 0 == info.error
        assert [
            DeviceCgiEndpoint(
                host="192.0.2.10",
                port=8080,
                scheme="http",
                auth_code="auth-code",
                verify_tls=False,
                debug=True,
            )
        ] == calls

    def test_device_profile_uses_same_endpoint_resolver(
        self, monkeypatch
    ) -> None:
        camera = Camera(config=_config())
        calls = []

        def fake_fetch_device_profile(
            endpoint: DeviceCgiEndpoint,
        ) -> CameraDeviceProfile:
            calls.append(endpoint)
            return _profile()

        monkeypatch.setattr(
            camera_api,
            "fetch_device_profile",
            fake_fetch_device_profile,
        )

        profile = camera.get_device_profile(
            port=8080,
            auth_code="auth-code",
            debug=True,
        )

        assert "1.2.3" == profile.firmware_version
        assert [
            DeviceCgiEndpoint(
                host="192.0.2.10",
                port=8080,
                scheme="http",
                auth_code="auth-code",
                verify_tls=False,
                debug=True,
            )
        ] == calls

    def test_additional_readonly_methods_use_same_endpoint_resolver(
        self, monkeypatch
    ) -> None:
        camera = Camera(config=_config())
        calls = []

        def fake_fetch_product_info(
            endpoint: DeviceCgiEndpoint,
        ) -> CameraDeviceProductInfo:
            calls.append(("product", endpoint))
            return CameraDeviceProductInfo(error=0, model="IDS9483PW")

        def fake_fetch_time_info(
            endpoint: DeviceCgiEndpoint,
        ) -> CameraDeviceTimeInfo:
            calls.append(("time", endpoint))
            return CameraDeviceTimeInfo(error=0, time_zone="Europe/Moscow")

        def fake_fetch_stream_key_info(
            endpoint: DeviceCgiEndpoint,
        ) -> CameraDeviceStreamKeyInfo:
            calls.append(("streamkey", endpoint))
            return CameraDeviceStreamKeyInfo(error=0, key="stream-key")

        def fake_fetch_qr_code_info(
            endpoint: DeviceCgiEndpoint,
        ) -> CameraDeviceQrCodeInfo:
            calls.append(("qrcode", endpoint))
            return CameraDeviceQrCodeInfo(error=0, qr_code="device-qr")

        def fake_fetch_alarm_channel_info(
            endpoint: DeviceCgiEndpoint,
        ) -> CameraDeviceAlarmChannelInfo:
            calls.append(("alarm-channel", endpoint))
            return CameraDeviceAlarmChannelInfo(error=0)

        def fake_fetch_alarm_motion_detection_info(
            endpoint: DeviceCgiEndpoint,
            *,
            channel_id: int = 1,
        ) -> CameraDeviceAlarmMotionDetectionInfo:
            calls.append(("alarm-motion", endpoint, channel_id))
            return CameraDeviceAlarmMotionDetectionInfo(
                error=0,
                channel_id=channel_id,
                sensitivity=5,
            )

        def fake_fetch_alarm_input_info(
            endpoint: DeviceCgiEndpoint,
            *,
            channel_id: int = -1,
        ) -> CameraDeviceAlarmInputInfo:
            calls.append(("alarm-input", endpoint, channel_id))
            return CameraDeviceAlarmInputInfo(error=0)

        def fake_fetch_alarm_video_lost_info(
            endpoint: DeviceCgiEndpoint,
            *,
            channel_id: int = 1,
        ) -> CameraDeviceAlarmVideoLostInfo:
            calls.append(("alarm-video-lost", endpoint, channel_id))
            return CameraDeviceAlarmVideoLostInfo(
                error=0,
                channel_id=channel_id,
                enabled=True,
            )

        def fake_fetch_alarm_video_shelter_info(
            endpoint: DeviceCgiEndpoint,
            *,
            channel_id: int = 1,
        ) -> CameraDeviceAlarmVideoShelterInfo:
            calls.append(("alarm-video-shelter", endpoint, channel_id))
            return CameraDeviceAlarmVideoShelterInfo(
                error=0,
                channel_id=channel_id,
                sensitivity=4,
            )

        def fake_fetch_record_config_info(
            endpoint: DeviceCgiEndpoint,
            *,
            channel_id: int = 1,
        ) -> CameraDeviceRecordConfigInfo:
            calls.append(("record", endpoint, channel_id))
            return CameraDeviceRecordConfigInfo(error=0, channel_id=channel_id)

        def fake_fetch_record_session_info(
            endpoint: DeviceCgiEndpoint,
            *,
            start_time: str,
            end_time: str,
            channel_id: int = 1,
            file_type: str = "all",
            occur_type: str = "all",
            stream: str = "all",
        ) -> CameraDeviceRecordSessionInfo:
            calls.append(
                (
                    "record-session",
                    endpoint,
                    start_time,
                    end_time,
                    channel_id,
                    file_type,
                    occur_type,
                    stream,
                )
            )
            return CameraDeviceRecordSessionInfo(
                error=0,
                session_id="archive-session-1",
            )

        def fake_fetch_record_message_info(
            endpoint: DeviceCgiEndpoint,
            *,
            session_id: str,
        ) -> CameraDeviceRecordMessageInfo:
            calls.append(("record-message", endpoint, session_id))
            return CameraDeviceRecordMessageInfo(error=0)

        def fake_fetch_record_list_info(
            endpoint: DeviceCgiEndpoint,
            *,
            start_time: str,
            end_time: str,
            channel_id: int = 1,
            file_type: str = "all",
            occur_type: str = "all",
            stream: str = "all",
            max_pages: int = 32,
        ) -> CameraDeviceRecordListInfo:
            calls.append(
                (
                    "record-list",
                    endpoint,
                    start_time,
                    end_time,
                    channel_id,
                    file_type,
                    occur_type,
                    stream,
                    max_pages,
                )
            )
            return CameraDeviceRecordListInfo(
                error=0,
                session_id="archive-session-1",
                records=[CameraDeviceRecordFileInfo(file_name="record.mp4")],
                completed=True,
            )

        def fake_fetch_record_alarm_info(
            endpoint: DeviceCgiEndpoint,
            *,
            timestamp: str,
            channel_id: int = 1,
            file_type: str = "all",
            occur_type: str = "all",
            stream: str = "all",
            alarm_type: int | None = None,
            alarm_id: str | None = None,
        ) -> CameraDeviceRecordAlarmInfo:
            calls.append(
                (
                    "record-alarm",
                    endpoint,
                    timestamp,
                    channel_id,
                    file_type,
                    occur_type,
                    stream,
                    alarm_type,
                    alarm_id,
                )
            )
            return CameraDeviceRecordAlarmInfo(
                error=0,
                records=[CameraDeviceRecordFileInfo(file_name="alarm.mp4")],
            )

        def fake_fetch_wifi_list_info(
            endpoint: DeviceCgiEndpoint,
        ) -> CameraDeviceWifiListInfo:
            calls.append(("wifi", endpoint))
            return CameraDeviceWifiListInfo(error=0)

        def fake_fetch_screen_flip_info(
            endpoint: DeviceCgiEndpoint,
        ) -> CameraDeviceScreenFlipInfo:
            calls.append(("screen", endpoint))
            return CameraDeviceScreenFlipInfo(error=0, state=1)

        def fake_fetch_video_switch_info(
            endpoint: DeviceCgiEndpoint,
        ) -> CameraDeviceVideoSwitchInfo:
            calls.append(("switch", endpoint))
            return CameraDeviceVideoSwitchInfo(error=0, is_on=True)

        def fake_fetch_time_title_info(
            endpoint: DeviceCgiEndpoint,
        ) -> CameraDeviceTimeTitleInfo:
            calls.append(("title", endpoint))
            return CameraDeviceTimeTitleInfo(error=0)

        monkeypatch.setattr(
            camera_api,
            "fetch_product_info",
            fake_fetch_product_info,
        )
        monkeypatch.setattr(
            camera_api,
            "fetch_time_info",
            fake_fetch_time_info,
        )
        monkeypatch.setattr(
            camera_api,
            "fetch_stream_key_info",
            fake_fetch_stream_key_info,
        )
        monkeypatch.setattr(
            camera_api,
            "fetch_qr_code_info",
            fake_fetch_qr_code_info,
        )
        monkeypatch.setattr(
            camera_api,
            "fetch_alarm_channel_info",
            fake_fetch_alarm_channel_info,
        )
        monkeypatch.setattr(
            camera_api,
            "fetch_alarm_motion_detection_info",
            fake_fetch_alarm_motion_detection_info,
        )
        monkeypatch.setattr(
            camera_api,
            "fetch_alarm_input_info",
            fake_fetch_alarm_input_info,
        )
        monkeypatch.setattr(
            camera_api,
            "fetch_alarm_video_lost_info",
            fake_fetch_alarm_video_lost_info,
        )
        monkeypatch.setattr(
            camera_api,
            "fetch_alarm_video_shelter_info",
            fake_fetch_alarm_video_shelter_info,
        )
        monkeypatch.setattr(
            camera_api,
            "fetch_record_config_info",
            fake_fetch_record_config_info,
        )
        monkeypatch.setattr(
            camera_api,
            "fetch_record_session_info",
            fake_fetch_record_session_info,
        )
        monkeypatch.setattr(
            camera_api,
            "fetch_record_message_info",
            fake_fetch_record_message_info,
        )
        monkeypatch.setattr(
            camera_api,
            "fetch_record_list_info",
            fake_fetch_record_list_info,
        )
        monkeypatch.setattr(
            camera_api,
            "fetch_record_alarm_info",
            fake_fetch_record_alarm_info,
        )
        monkeypatch.setattr(
            camera_api,
            "fetch_wifi_list_info",
            fake_fetch_wifi_list_info,
        )
        monkeypatch.setattr(
            camera_api,
            "fetch_screen_flip_info",
            fake_fetch_screen_flip_info,
        )
        monkeypatch.setattr(
            camera_api,
            "fetch_video_switch_info",
            fake_fetch_video_switch_info,
        )
        monkeypatch.setattr(
            camera_api,
            "fetch_time_title_info",
            fake_fetch_time_title_info,
        )

        assert (
            "IDS9483PW"
            == camera.get_product_info(port=8080, auth_code="auth-code").model
        )
        assert (
            "Europe/Moscow"
            == camera.get_time_info(port=8080, auth_code="auth-code").time_zone
        )
        assert (
            "stream-key"
            == camera.get_stream_key_info(port=8080, auth_code="auth-code").key
        )
        assert (
            "device-qr"
            == camera.get_qr_code_info(
                port=8080, auth_code="auth-code"
            ).qr_code
        )
        assert (
            0
            == camera.get_alarm_channel_info(
                port=8080,
                auth_code="auth-code",
            ).error
        )
        assert (
            5
            == camera.get_alarm_motion_detection_info(
                channel_id=2,
                port=8080,
                auth_code="auth-code",
            ).sensitivity
        )
        assert (
            0
            == camera.get_alarm_input_info(
                channel_id=2,
                port=8080,
                auth_code="auth-code",
            ).error
        )
        assert camera.get_alarm_video_lost_info(
            channel_id=2,
            port=8080,
            auth_code="auth-code",
        ).enabled
        assert (
            4
            == camera.get_alarm_video_shelter_info(
                channel_id=2,
                port=8080,
                auth_code="auth-code",
            ).sensitivity
        )
        assert (
            2
            == camera.get_record_config_info(
                channel_id=2,
                port=8080,
                auth_code="auth-code",
            ).channel_id
        )
        assert (
            "archive-session-1"
            == camera.get_record_session_info(
                start_time="2026-06-24T00:00:00",
                end_time="2026-06-24T23:59:59",
                channel_id=2,
                file_type="video",
                occur_type="standard",
                stream="main",
                port=8080,
                auth_code="auth-code",
            ).session_id
        )
        assert (
            0
            == camera.get_record_message_info(
                session_id="archive-session-1",
                port=8080,
                auth_code="auth-code",
            ).error
        )
        assert (
            "record.mp4"
            == camera.list_record_files(
                start_time="2026-06-24T00:00:00",
                end_time="2026-06-24T23:59:59",
                channel_id=2,
                file_type="video",
                occur_type="standard",
                stream="main",
                max_pages=8,
                port=8080,
                auth_code="auth-code",
            )
            .records[0]
            .file_name
        )
        assert (
            "alarm.mp4"
            == camera.get_record_alarm_info(
                timestamp="2026-06-24T01:00:00",
                channel_id=2,
                file_type="video",
                occur_type="alarm",
                stream="main",
                alarm_type=7,
                alarm_id="alarm-1",
                port=8080,
                auth_code="auth-code",
            )
            .records[0]
            .file_name
        )
        assert (
            0 == camera.get_wifi_list(port=8080, auth_code="auth-code").error
        )
        assert (
            1
            == camera.get_screen_flip_info(
                port=8080, auth_code="auth-code"
            ).state
        )
        assert camera.get_video_switch_info(
            port=8080, auth_code="auth-code"
        ).is_on
        assert (
            0
            == camera.get_time_title_info(
                port=8080, auth_code="auth-code"
            ).error
        )

        expected_endpoint = DeviceCgiEndpoint(
            host="192.0.2.10",
            port=8080,
            scheme="http",
            auth_code="auth-code",
            verify_tls=False,
            debug=False,
        )
        assert [
            ("product", expected_endpoint),
            ("time", expected_endpoint),
            ("streamkey", expected_endpoint),
            ("qrcode", expected_endpoint),
            ("alarm-channel", expected_endpoint),
            ("alarm-motion", expected_endpoint, 2),
            ("alarm-input", expected_endpoint, 2),
            ("alarm-video-lost", expected_endpoint, 2),
            ("alarm-video-shelter", expected_endpoint, 2),
            ("record", expected_endpoint, 2),
            (
                "record-session",
                expected_endpoint,
                "2026-06-24T00:00:00",
                "2026-06-24T23:59:59",
                2,
                "video",
                "standard",
                "main",
            ),
            ("record-message", expected_endpoint, "archive-session-1"),
            (
                "record-list",
                expected_endpoint,
                "2026-06-24T00:00:00",
                "2026-06-24T23:59:59",
                2,
                "video",
                "standard",
                "main",
                8,
            ),
            (
                "record-alarm",
                expected_endpoint,
                "2026-06-24T01:00:00",
                2,
                "video",
                "alarm",
                "main",
                7,
                "alarm-1",
            ),
            ("wifi", expected_endpoint),
            ("screen", expected_endpoint),
            ("switch", expected_endpoint),
            ("title", expected_endpoint),
        ] == calls

    def test_record_list_info_follows_native_result_loop(
        self, monkeypatch
    ) -> None:
        endpoint = DeviceCgiEndpoint(
            host="192.0.2.10",
            auth_code="auth-code",
        )
        calls = []
        pages = [
            CameraDeviceRecordMessageInfo(
                error=0,
                result=1,
                records=[CameraDeviceRecordFileInfo(file_name="first.mp4")],
            ),
            CameraDeviceRecordMessageInfo(
                error=0,
                result=0,
                records=[CameraDeviceRecordFileInfo(file_name="second.mp4")],
            ),
        ]

        def fake_fetch_record_session_info(
            endpoint: DeviceCgiEndpoint,
            *,
            start_time: str,
            end_time: str,
            channel_id: int = 1,
            file_type: str = "all",
            occur_type: str = "all",
            stream: str = "all",
        ) -> CameraDeviceRecordSessionInfo:
            calls.append(
                (
                    "session",
                    endpoint,
                    start_time,
                    end_time,
                    channel_id,
                    file_type,
                    occur_type,
                    stream,
                )
            )
            return CameraDeviceRecordSessionInfo(
                error=0,
                session_id="archive-session-1",
            )

        def fake_fetch_record_message_info(
            endpoint: DeviceCgiEndpoint,
            *,
            session_id: str,
        ) -> CameraDeviceRecordMessageInfo:
            calls.append(("message", endpoint, session_id))
            return pages.pop(0)

        monkeypatch.setattr(
            device_cgi_service,
            "fetch_record_session_info",
            fake_fetch_record_session_info,
        )
        monkeypatch.setattr(
            device_cgi_service,
            "fetch_record_message_info",
            fake_fetch_record_message_info,
        )

        result = device_cgi_service.fetch_record_list_info(
            endpoint,
            start_time="2026-06-24T00:00:00",
            end_time="2026-06-24T23:59:59",
            channel_id=2,
            file_type="video",
            occur_type="standard",
            stream="main",
        )

        assert result.completed
        assert "archive-session-1" == result.session_id
        assert ["first.mp4", "second.mp4"] == [
            record.file_name for record in result.records
        ]
        assert [
            (
                "session",
                endpoint,
                "2026-06-24T00:00:00",
                "2026-06-24T23:59:59",
                2,
                "video",
                "standard",
                "main",
            ),
            ("message", endpoint, "archive-session-1"),
            ("message", endpoint, "archive-session-1"),
        ] == calls

    def test_readonly_methods_use_config_auth_code_without_cloud_lookup(
        self, monkeypatch
    ) -> None:
        camera = Camera(config=_config())
        calls = []

        class FakeConnector:
            def fetch_credentials(self) -> object:
                raise AssertionError("local CGI methods must not call cloud")

        camera.connector = FakeConnector()

        def fake_fetch_product_info(
            endpoint: DeviceCgiEndpoint,
        ) -> CameraDeviceProductInfo:
            calls.append(endpoint)
            return CameraDeviceProductInfo(error=0)

        monkeypatch.setattr(
            camera_api,
            "fetch_product_info",
            fake_fetch_product_info,
        )

        assert 0 == camera.get_product_info(port=8080).error
        assert [
            DeviceCgiEndpoint(
                host="192.0.2.10",
                port=8080,
                scheme="http",
                auth_code="config-auth-code",
                verify_tls=False,
                debug=False,
            )
        ] == calls

    def test_device_host_is_required_for_local_cgi_methods(self) -> None:
        camera = Camera(config=_config(device_host=""))

        with pytest.raises(ConfigurationError, match="CAMERA_DEVICE_HOST"):
            camera.get_storage_info(auth_code="auth-code")

    def test_auth_code_is_required_for_local_cgi_methods(self) -> None:
        camera = Camera(config=_config(auth_code=""))

        with pytest.raises(ConfigurationError, match="AUTH_CODE"):
            camera.get_storage_info()

    def test_device_profile_exposes_command_support_statuses(self) -> None:
        profile = _profile(
            product=CameraDeviceProductInfo(
                error=0,
                version="V401",
                raw=_raw_response(
                    command="get.product.info",
                    error=0,
                    content={"info": {"version": "V401"}},
                ),
            ),
            wifi=CameraDeviceWifiListInfo(
                error=-1,
                raw=_raw_response(
                    command="get.wifi.list",
                    error=-1,
                    content={},
                ),
            ),
            capabilities=CameraDeviceCapabilitiesInfo(
                error=401,
                raw=_raw_response(
                    command="get.system.ability",
                    error=401,
                    content={},
                ),
            ),
        )

        assert "V401" == profile.firmware_version
        assert ("get.product.info",) == profile.supported_commands
        assert ("get.wifi.list",) == profile.unsupported_commands
        assert ("get.system.ability",) == profile.failed_commands
        assert profile.status_by_command["get.wifi.list"].unsupported

    def test_device_profile_exposes_media_and_network_helpers(self) -> None:
        profile = _profile(
            video_config=_video_config(),
            network=CameraDeviceNetworkInfo(
                error=0,
                lan_interfaces=[
                    CameraDeviceLanInfo(
                        name="eth0",
                        ip_address="192.0.2.10",
                        gateway="192.0.2.1",
                        dhcp=True,
                    )
                ],
            ),
        )

        assert ("1", "2") == tuple(
            channel.channel_id for channel in profile.video_channels
        )
        assert (
            ("1", "mainstream", "1920x1080", 25),
            ("1", "substream", "640x360", 15),
            ("2", "mainstream", "1280x720", 20),
        ) == tuple(
            (
                stream.channel_id,
                stream.stream_name,
                stream.resolution,
                stream.fps,
            )
            for stream in profile.stream_profiles
        )
        assert ("192.0.2.10",) == tuple(
            interface.ip_address for interface in profile.network_interfaces
        )

    def test_device_profile_falls_back_to_top_level_network_fields(
        self,
    ) -> None:
        profile = _profile(
            network=CameraDeviceNetworkInfo(
                error=0,
                address="192.0.2.20",
                subnet_mask="255.255.255.0",
                gateway="192.0.2.1",
                dhcp=False,
            )
        )

        assert 1 == len(profile.network_interfaces)
        assert "192.0.2.20" == profile.network_interfaces[0].ip_address
        assert profile.network_interfaces[0].dhcp is False

    def test_media_and_network_convenience_methods_use_local_cgi(
        self, monkeypatch
    ) -> None:
        camera = Camera(config=_config())
        calls = []

        def fake_fetch_video_config_info(
            endpoint: DeviceCgiEndpoint,
        ) -> CameraDeviceVideoConfigInfo:
            calls.append(("video", endpoint))
            return _video_config()

        def fake_fetch_network_info(
            endpoint: DeviceCgiEndpoint,
        ) -> CameraDeviceNetworkInfo:
            calls.append(("network", endpoint))
            return CameraDeviceNetworkInfo(
                error=0,
                address="192.0.2.30",
                subnet_mask="255.255.255.0",
                gateway="192.0.2.1",
                dhcp=True,
            )

        monkeypatch.setattr(
            camera_api,
            "fetch_video_config_info",
            fake_fetch_video_config_info,
        )
        monkeypatch.setattr(
            camera_api,
            "fetch_network_info",
            fake_fetch_network_info,
        )

        channels = camera.get_video_channels(
            port=8080,
            auth_code="auth-code",
        )
        all_profiles = camera.get_stream_profiles(
            port=8080,
            auth_code="auth-code",
        )
        channel_profiles = camera.get_stream_profiles(
            channel_id=2,
            port=8080,
            auth_code="auth-code",
        )
        interfaces = camera.get_network_interfaces(
            port=8080,
            auth_code="auth-code",
        )

        assert ("1", "2") == tuple(channel.channel_id for channel in channels)
        assert 3 == len(all_profiles)
        assert ("2",) == tuple(
            profile.channel_id for profile in channel_profiles
        )
        assert ("192.0.2.30",) == tuple(
            interface.ip_address for interface in interfaces
        )

        expected_endpoint = DeviceCgiEndpoint(
            host="192.0.2.10",
            port=8080,
            scheme="http",
            auth_code="auth-code",
            verify_tls=False,
            debug=False,
        )
        assert [
            ("video", expected_endpoint),
            ("video", expected_endpoint),
            ("video", expected_endpoint),
            ("network", expected_endpoint),
        ] == calls

    def test_network_base_info_uses_same_endpoint_resolver(
        self,
        monkeypatch,
    ) -> None:
        camera = Camera(config=_config())
        calls = []

        def fake_fetch_network_base_info(
            endpoint: DeviceCgiEndpoint,
        ) -> CameraDeviceNetworkBaseInfo:
            calls.append(endpoint)
            return CameraDeviceNetworkBaseInfo(
                error=0,
                media_port=34567,
                rtsp_port=554,
            )

        monkeypatch.setattr(
            camera_api,
            "fetch_network_base_info",
            fake_fetch_network_base_info,
        )

        info = camera.get_network_base_info(
            port=8080,
            auth_code="auth-code",
            debug=True,
        )

        assert 34567 == info.media_port
        assert 554 == info.rtsp_port
        assert [
            DeviceCgiEndpoint(
                host="192.0.2.10",
                port=8080,
                scheme="http",
                auth_code="auth-code",
                verify_tls=False,
                debug=True,
            )
        ] == calls


def _raw_response(
    *,
    command: str,
    error: int,
    content: dict[str, Any],
) -> DeviceCgiResponse:
    return DeviceCgiResponse(
        command=command,
        error=error,
        content=content,
        raw_xml="<envelope />",
    )


def _profile(
    *,
    all_info: CameraDeviceAllInfo | None = None,
    product: CameraDeviceProductInfo | None = None,
    time: CameraDeviceTimeInfo | None = None,
    storage: CameraDeviceStorageInfo | None = None,
    network: CameraDeviceNetworkInfo | None = None,
    general: CameraDeviceGeneralInfo | None = None,
    capabilities: CameraDeviceCapabilitiesInfo | None = None,
    video_config: CameraDeviceVideoConfigInfo | None = None,
    wifi: CameraDeviceWifiListInfo | None = None,
    screen_flip: CameraDeviceScreenFlipInfo | None = None,
    video_switch: CameraDeviceVideoSwitchInfo | None = None,
    time_title: CameraDeviceTimeTitleInfo | None = None,
) -> CameraDeviceProfile:
    return CameraDeviceProfile(
        all_info=all_info or CameraDeviceAllInfo(error=0),
        product=product or CameraDeviceProductInfo(error=0, version="1.2.3"),
        time=time or CameraDeviceTimeInfo(error=0),
        storage=storage
        or CameraDeviceStorageInfo(error=0, total_sum=None, free_sum=None),
        network=network or CameraDeviceNetworkInfo(error=0),
        general=general or CameraDeviceGeneralInfo(error=0),
        capabilities=capabilities or CameraDeviceCapabilitiesInfo(error=0),
        video_config=video_config or CameraDeviceVideoConfigInfo(error=0),
        wifi=wifi or CameraDeviceWifiListInfo(error=0),
        screen_flip=screen_flip or CameraDeviceScreenFlipInfo(error=0),
        video_switch=video_switch or CameraDeviceVideoSwitchInfo(error=0),
        time_title=time_title or CameraDeviceTimeTitleInfo(error=0),
        command_statuses=tuple(
            status
            for status in (
                _status_for(product, "get.product.info"),
                _status_for(wifi, "get.wifi.list"),
                _status_for(capabilities, "get.system.ability"),
            )
            if status is not None
        ),
    )


def _video_config() -> CameraDeviceVideoConfigInfo:
    return CameraDeviceVideoConfigInfo(
        error=0,
        channels=[
            CameraDeviceVideoChannelInfo(
                channel_id="1",
                name="Front Door",
                streams=[
                    CameraDeviceVideoStreamInfo(
                        name="mainstream",
                        enabled=True,
                        compression="H.264",
                        resolution="1920x1080",
                        fps=25,
                        bitrate=2048,
                    ),
                    CameraDeviceVideoStreamInfo(
                        name="substream",
                        enabled=True,
                        compression="H.264",
                        resolution="640x360",
                        fps=15,
                        bitrate=512,
                    ),
                ],
            ),
            CameraDeviceVideoChannelInfo(
                channel_id="2",
                name="Second Channel",
                streams=[
                    CameraDeviceVideoStreamInfo(
                        name="mainstream",
                        enabled=True,
                        compression="H.264",
                        resolution="1280x720",
                        fps=20,
                        bitrate=1024,
                    )
                ],
            ),
        ],
    )


def _status_for(
    response: CameraDeviceProfileResponse | None,
    command: str,
) -> CameraDeviceCommandStatus | None:
    if response is None:
        return None
    return command_status_for_response(command, response)
