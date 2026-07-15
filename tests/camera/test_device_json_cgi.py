from quii_helper.camera import (
    Camera,
    CameraDeviceAlarmDetailChannelInfo,
    CameraDeviceAlarmDetailInfo,
    CameraDeviceAlarmStatusInfo,
    CameraDeviceAudioSessionInfo,
    CameraDeviceAudioVolumeInfo,
    CameraDeviceAudioVolumeRange,
    CameraDeviceBabysitterStateInfo,
    CameraDeviceCityCoordinateInfo,
    CameraDeviceFloodlightInfo,
    CameraDeviceFloodlightScheduleDayInfo,
    CameraDeviceFloodlightScheduleInfo,
    CameraDeviceFloodlightSwitchInfo,
    CameraDeviceHardwareInfo,
    CameraDeviceJsonFpsModeInfo,
    CameraDeviceLightInfo,
    CameraDeviceLightItemInfo,
    CameraDeviceLightRoomInfo,
    CameraDeviceLockInfo,
    CameraDeviceLockStatusInfo,
    CameraDevicePirConfigInfo,
    CameraDevicePirScheduleDayInfo,
    CameraDevicePirScheduleSlotInfo,
    CameraDeviceSmartSwitchInfo,
    CameraDeviceSmartSwitchItemInfo,
    CameraDeviceSmartSwitchRoomInfo,
    CameraDeviceThirdPartyPushInfo,
    CameraDeviceThirdPartyPushScheduleDayInfo,
    CameraDeviceThirdPartyPushScheduleSlotInfo,
    CameraDeviceVoiceFileInfo,
    CameraDeviceVoiceMessageInfo,
)
from quii_helper.camera import api as camera_api
from quii_helper.camera.device_cgi import DeviceCgiEndpoint
from quii_helper.config import AutonomousConfig


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


class CameraDeviceJsonCgiTests:
    def test_alarm_detail_info_uses_same_endpoint_resolver(
        self,
        monkeypatch,
    ) -> None:
        camera = Camera(config=_config())
        calls = []

        def fake_fetch_alarm_detail_info(
            endpoint: DeviceCgiEndpoint,
            *,
            alarm_type: int,
        ) -> CameraDeviceAlarmDetailInfo:
            calls.append((endpoint, alarm_type))
            return CameraDeviceAlarmDetailInfo(
                error=0,
                alarm_type=alarm_type,
                channel=CameraDeviceAlarmDetailChannelInfo(channel_id=1),
            )

        monkeypatch.setattr(
            camera_api,
            "fetch_alarm_detail_info",
            fake_fetch_alarm_detail_info,
        )

        info = camera.get_alarm_detail_info(
            alarm_type=2,
            port=8080,
            auth_code="auth-code",
            debug=True,
        )

        assert 2 == info.alarm_type
        assert info.channel is not None
        assert 1 == info.channel.channel_id
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

    def test_alarm_status_info_uses_same_endpoint_resolver(
        self,
        monkeypatch,
    ) -> None:
        camera = Camera(config=_config())
        calls = []

        def fake_fetch_alarm_status_info(
            endpoint: DeviceCgiEndpoint,
        ) -> CameraDeviceAlarmStatusInfo:
            calls.append(endpoint)
            return CameraDeviceAlarmStatusInfo(
                error=0,
                status="on",
                is_on=True,
            )

        monkeypatch.setattr(
            camera_api,
            "fetch_alarm_status_info",
            fake_fetch_alarm_status_info,
        )

        info = camera.get_alarm_status_info(
            port=8080,
            auth_code="auth-code",
            debug=True,
        )

        assert "on" == info.status
        assert info.is_on is True
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

    def test_audio_volume_info_uses_same_endpoint_resolver(
        self,
        monkeypatch,
    ) -> None:
        camera = Camera(config=_config())
        calls = []

        def fake_fetch_audio_volume_info(
            endpoint: DeviceCgiEndpoint,
        ) -> CameraDeviceAudioVolumeInfo:
            calls.append(endpoint)
            return CameraDeviceAudioVolumeInfo(
                error=0,
                prompt=CameraDeviceAudioVolumeRange(level=7),
            )

        monkeypatch.setattr(
            camera_api,
            "fetch_audio_volume_info",
            fake_fetch_audio_volume_info,
        )

        info = camera.get_audio_volume_info(
            port=8080,
            auth_code="auth-code",
            debug=True,
        )

        assert info.prompt is not None
        assert 7 == info.prompt.level
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

    def test_audio_session_info_uses_same_endpoint_resolver(
        self,
        monkeypatch,
    ) -> None:
        camera = Camera(config=_config())
        calls = []

        def fake_fetch_audio_session_info(
            endpoint: DeviceCgiEndpoint,
        ) -> CameraDeviceAudioSessionInfo:
            calls.append(endpoint)
            return CameraDeviceAudioSessionInfo(
                error=0,
                session="audio-session-id",
                file_id="voice-file-id",
            )

        monkeypatch.setattr(
            camera_api,
            "fetch_audio_session_info",
            fake_fetch_audio_session_info,
        )

        info = camera.get_audio_session_info(
            port=8080,
            auth_code="auth-code",
            debug=True,
        )

        assert "audio-session-id" == info.session
        assert "voice-file-id" == info.file_id
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

    def test_json_fps_mode_info_uses_same_endpoint_resolver(
        self,
        monkeypatch,
    ) -> None:
        camera = Camera(config=_config())
        calls = []

        def fake_fetch_json_fps_mode_info(
            endpoint: DeviceCgiEndpoint,
        ) -> CameraDeviceJsonFpsModeInfo:
            calls.append(endpoint)
            return CameraDeviceJsonFpsModeInfo(error=0, mode=2)

        monkeypatch.setattr(
            camera_api,
            "fetch_json_fps_mode_info",
            fake_fetch_json_fps_mode_info,
        )

        info = camera.get_json_fps_mode_info(
            port=8080,
            auth_code="auth-code",
            debug=True,
        )

        assert 2 == info.mode
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

    def test_hardware_info_uses_same_endpoint_resolver(
        self,
        monkeypatch,
    ) -> None:
        camera = Camera(config=_config())
        calls = []

        def fake_fetch_hardware_info(
            endpoint: DeviceCgiEndpoint,
        ) -> CameraDeviceHardwareInfo:
            calls.append(endpoint)
            return CameraDeviceHardwareInfo(error=0, battery_quantity=87)

        monkeypatch.setattr(
            camera_api,
            "fetch_hardware_info",
            fake_fetch_hardware_info,
        )

        info = camera.get_hardware_info(
            port=8080,
            auth_code="auth-code",
            debug=True,
        )

        assert 87 == info.battery_quantity
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

    def test_light_info_uses_same_endpoint_resolver(
        self,
        monkeypatch,
    ) -> None:
        camera = Camera(config=_config())
        calls = []

        def fake_fetch_light_info(
            endpoint: DeviceCgiEndpoint,
        ) -> CameraDeviceLightInfo:
            calls.append(endpoint)
            return CameraDeviceLightInfo(
                error=0,
                rooms=[
                    CameraDeviceLightRoomInfo(
                        name="Hall",
                        lights=[CameraDeviceLightItemInfo(name="Main")],
                    )
                ],
            )

        monkeypatch.setattr(
            camera_api,
            "fetch_light_info",
            fake_fetch_light_info,
        )

        info = camera.get_light_info(
            port=8080,
            auth_code="auth-code",
            debug=True,
        )

        assert "Main" == info.rooms[0].lights[0].name
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

    def test_babysitter_state_info_uses_same_endpoint_resolver(
        self,
        monkeypatch,
    ) -> None:
        camera = Camera(config=_config())
        calls = []

        def fake_fetch_babysitter_state_info(
            endpoint: DeviceCgiEndpoint,
        ) -> CameraDeviceBabysitterStateInfo:
            calls.append(endpoint)
            return CameraDeviceBabysitterStateInfo(error=0, mode=True)

        monkeypatch.setattr(
            camera_api,
            "fetch_babysitter_state_info",
            fake_fetch_babysitter_state_info,
        )

        info = camera.get_babysitter_state_info(
            port=8080,
            auth_code="auth-code",
            debug=True,
        )

        assert info.mode is True
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

    def test_pir_config_info_uses_same_endpoint_resolver(
        self,
        monkeypatch,
    ) -> None:
        camera = Camera(config=_config())
        calls = []

        def fake_fetch_pir_config_info(
            endpoint: DeviceCgiEndpoint,
        ) -> CameraDevicePirConfigInfo:
            calls.append(endpoint)
            return CameraDevicePirConfigInfo(
                error=0,
                enabled=True,
                schedule=[
                    CameraDevicePirScheduleDayInfo(
                        week="monday",
                        slots=[
                            CameraDevicePirScheduleSlotInfo(
                                section="time1",
                                enabled=True,
                            )
                        ],
                    )
                ],
            )

        monkeypatch.setattr(
            camera_api,
            "fetch_pir_config_info",
            fake_fetch_pir_config_info,
        )

        info = camera.get_pir_config_info(
            port=8080,
            auth_code="auth-code",
            debug=True,
        )

        assert info.enabled is True
        assert "time1" == info.schedule[0].slots[0].section
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

    def test_smart_switch_info_uses_same_endpoint_resolver(
        self,
        monkeypatch,
    ) -> None:
        camera = Camera(config=_config())
        calls = []

        def fake_fetch_smart_switch_info(
            endpoint: DeviceCgiEndpoint,
        ) -> CameraDeviceSmartSwitchInfo:
            calls.append(endpoint)
            return CameraDeviceSmartSwitchInfo(
                error=0,
                rooms=[
                    CameraDeviceSmartSwitchRoomInfo(
                        name="Hall",
                        switches=[
                            CameraDeviceSmartSwitchItemInfo(name="Relay")
                        ],
                    )
                ],
            )

        monkeypatch.setattr(
            camera_api,
            "fetch_smart_switch_info",
            fake_fetch_smart_switch_info,
        )

        info = camera.get_smart_switch_info(
            port=8080,
            auth_code="auth-code",
            debug=True,
        )

        assert "Relay" == info.rooms[0].switches[0].name
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

    def test_third_party_push_info_uses_same_endpoint_resolver(
        self,
        monkeypatch,
    ) -> None:
        camera = Camera(config=_config())
        calls = []

        def fake_fetch_third_party_push_info(
            endpoint: DeviceCgiEndpoint,
        ) -> CameraDeviceThirdPartyPushInfo:
            calls.append(endpoint)
            return CameraDeviceThirdPartyPushInfo(
                error=0,
                account="door@example.com",
                event_types=[2, 19],
                schedule=[
                    CameraDeviceThirdPartyPushScheduleDayInfo(
                        week="monday",
                        slots=[
                            CameraDeviceThirdPartyPushScheduleSlotInfo(
                                section="time1",
                                enabled=True,
                            )
                        ],
                    )
                ],
            )

        monkeypatch.setattr(
            camera_api,
            "fetch_third_party_push_info",
            fake_fetch_third_party_push_info,
        )

        info = camera.get_third_party_push_info(
            port=8080,
            auth_code="auth-code",
            debug=True,
        )

        assert "door@example.com" == info.account
        assert [2, 19] == info.event_types
        assert "time1" == info.schedule[0].slots[0].section
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

    def test_lock_status_info_uses_same_endpoint_resolver(
        self,
        monkeypatch,
    ) -> None:
        camera = Camera(config=_config())
        calls = []

        def fake_fetch_lock_status_info(
            endpoint: DeviceCgiEndpoint,
        ) -> CameraDeviceLockStatusInfo:
            calls.append(endpoint)
            return CameraDeviceLockStatusInfo(
                error=0,
                locks=[CameraDeviceLockInfo(lock_id=1, name="Main lock")],
            )

        monkeypatch.setattr(
            camera_api,
            "fetch_lock_status_info",
            fake_fetch_lock_status_info,
        )

        info = camera.get_lock_status_info(
            port=8080,
            auth_code="auth-code",
            debug=True,
        )

        assert 1 == info.locks[0].lock_id
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

    def test_floodlight_switch_info_uses_same_endpoint_resolver(
        self,
        monkeypatch,
    ) -> None:
        camera = Camera(config=_config())
        calls = []

        def fake_fetch_floodlight_switch_info(
            endpoint: DeviceCgiEndpoint,
        ) -> CameraDeviceFloodlightSwitchInfo:
            calls.append(endpoint)
            return CameraDeviceFloodlightSwitchInfo(
                error=0,
                lights=[CameraDeviceFloodlightInfo(code="floodlight-1")],
            )

        monkeypatch.setattr(
            camera_api,
            "fetch_floodlight_switch_info",
            fake_fetch_floodlight_switch_info,
        )

        info = camera.get_floodlight_switch_info(
            port=8080,
            auth_code="auth-code",
            debug=True,
        )

        assert "floodlight-1" == info.lights[0].code
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

    def test_floodlight_schedule_info_uses_same_endpoint_resolver(
        self,
        monkeypatch,
    ) -> None:
        camera = Camera(config=_config())
        calls = []

        def fake_fetch_floodlight_schedule_info(
            endpoint: DeviceCgiEndpoint,
        ) -> CameraDeviceFloodlightScheduleInfo:
            calls.append(endpoint)
            return CameraDeviceFloodlightScheduleInfo(
                error=0,
                sunrise="06:10:00",
                days=[CameraDeviceFloodlightScheduleDayInfo(week=1)],
            )

        monkeypatch.setattr(
            camera_api,
            "fetch_floodlight_schedule_info",
            fake_fetch_floodlight_schedule_info,
        )

        info = camera.get_floodlight_schedule_info(
            port=8080,
            auth_code="auth-code",
            debug=True,
        )

        assert "06:10:00" == info.sunrise
        assert 1 == info.days[0].week
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

    def test_city_coordinate_info_uses_same_endpoint_resolver(
        self,
        monkeypatch,
    ) -> None:
        camera = Camera(config=_config())
        calls = []

        def fake_fetch_city_coordinate_info(
            endpoint: DeviceCgiEndpoint,
        ) -> CameraDeviceCityCoordinateInfo:
            calls.append(endpoint)
            return CameraDeviceCityCoordinateInfo(
                error=0,
                latitude=55.7558,
                longitude=37.6173,
            )

        monkeypatch.setattr(
            camera_api,
            "fetch_city_coordinate_info",
            fake_fetch_city_coordinate_info,
        )

        info = camera.get_city_coordinate_info(
            port=8080,
            auth_code="auth-code",
            debug=True,
        )

        assert 55.7558 == info.latitude
        assert 37.6173 == info.longitude
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

    def test_voice_message_info_uses_same_endpoint_resolver(
        self,
        monkeypatch,
    ) -> None:
        camera = Camera(config=_config())
        calls = []

        def fake_fetch_voice_message_info(
            endpoint: DeviceCgiEndpoint,
        ) -> CameraDeviceVoiceMessageInfo:
            calls.append(endpoint)
            return CameraDeviceVoiceMessageInfo(
                error=0,
                files=[CameraDeviceVoiceFileInfo(file_id=1, name="Welcome")],
            )

        monkeypatch.setattr(
            camera_api,
            "fetch_voice_message_info",
            fake_fetch_voice_message_info,
        )

        info = camera.get_voice_message_info(
            port=8080,
            auth_code="auth-code",
            debug=True,
        )

        assert "Welcome" == info.files[0].name
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
