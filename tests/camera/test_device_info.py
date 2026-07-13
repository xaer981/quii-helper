from quii_helper.camera import Camera, CameraDeviceInfo
from quii_helper.camera import api as camera_api
from quii_helper.camera.metadata import camera_device_info_from_credentials
from quii_helper.cloud.devices import CloudDeviceListEntry
from quii_helper.config import AutonomousConfig, RuntimeCredentials


def _config() -> AutonomousConfig:
    return AutonomousConfig(
        device_id="device-config",
        cloud_account="account",
        cloud_password="password",
        service_url="https://service.example",
        auth_url="https://auth.example",
        oem="OEM",
        app_id=1,
        client_type=2,
        client_id="client-id",
        ip_region_id=3,
    )


def _credentials() -> RuntimeCredentials:
    return RuntimeCredentials(
        session_id="session",
        dynamic_password="secret-dynamic-password",
        data_encode_key="secret-data-key",
        auth_code="secret-auth-code",
        transparent_basedata="opaque-capabilities",
        raw={
            "token": {
                "device_id": "device-token",
                "channel_num": "4",
                "device_type": "doorphone",
                "model": "Marilyn",
                "is_hs_device": "1",
                "from_share": "0",
                "share_mode": "owner",
                "pwd_expired": "false",
            }
        },
    )


class _FakeConnector:
    def __init__(self) -> None:
        self.fetch_count = 0
        self.open_preview_count = 0

    def fetch_credentials(self) -> RuntimeCredentials:
        self.fetch_count += 1
        return _credentials()

    def open_preview(self, **_kwargs: object) -> object:
        self.open_preview_count += 1
        raise AssertionError("get_device_info must not open preview")


class CameraDeviceInfoTests:
    def test_device_info_from_credentials_maps_safe_cloud_fields(self) -> None:
        info = camera_device_info_from_credentials(_config(), _credentials())

        assert (
            CameraDeviceInfo(
                device_id="device-token",
                channel_count=4,
                device_type="doorphone",
                model="Marilyn",
                is_hs_device=True,
                from_share=False,
                share_mode="owner",
                password_expired=False,
                transparent_basedata="opaque-capabilities",
            )
            == info
        )

    def test_device_info_prefers_cloud_device_list_metadata(self) -> None:
        info = camera_device_info_from_credentials(
            _config(),
            _credentials(),
            cloud_device=CloudDeviceListEntry(
                device_id="device-list",
                name="Front Door",
                memo_name="Main entrance",
                channel_count=2,
                device_type="vhome-doorphone",
                model="Tantos Marilyn Wi-Fi s",
                is_hs_device=False,
                from_share=True,
                share_mode="shared",
                password_expired=True,
                transparent_basedata="list-capabilities",
            ),
        )

        assert "device-list" == info.device_id
        assert "Front Door" == info.name
        assert "Main entrance" == info.memo_name
        assert 2 == info.channel_count
        assert "vhome-doorphone" == info.device_type
        assert "Tantos Marilyn Wi-Fi s" == info.model
        assert info.is_hs_device is False
        assert info.from_share is True
        assert "shared" == info.share_mode
        assert info.password_expired is True
        assert "list-capabilities" == info.transparent_basedata

    def test_device_info_falls_back_to_config_device_id(self) -> None:
        credentials = _credentials()
        credentials.raw["token"]["device_id"] = ""

        info = camera_device_info_from_credentials(_config(), credentials)

        assert "device-config" == info.device_id

    def test_camera_get_device_info_fetches_cloud_list_without_preview(
        self, monkeypatch
    ) -> None:
        camera = Camera(config=_config())
        connector = _FakeConnector()
        camera.connector = connector
        device_list_calls = []

        def fake_fetch_cloud_device_list(
            config: AutonomousConfig,
            *,
            session_id: str,
        ) -> list[CloudDeviceListEntry]:
            device_list_calls.append((config, session_id))
            return [
                CloudDeviceListEntry(
                    device_id="device-config",
                    name="Front Door",
                    memo_name="",
                    channel_count=2,
                    device_type="doorphone",
                    model="Tantos Marilyn Wi-Fi s",
                    is_hs_device=False,
                    from_share=False,
                    share_mode="owner",
                    password_expired=False,
                    transparent_basedata="list-capabilities",
                )
            ]

        monkeypatch.setattr(
            camera_api,
            "fetch_cloud_device_list",
            fake_fetch_cloud_device_list,
        )

        info = camera.get_device_info()

        assert "device-config" == info.device_id
        assert "Front Door" == info.name
        assert "Tantos Marilyn Wi-Fi s" == info.model
        assert [(camera.config, "session")] == device_list_calls
        assert 1 == connector.fetch_count
        assert 0 == connector.open_preview_count
