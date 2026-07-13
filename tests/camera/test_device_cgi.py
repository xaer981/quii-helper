from quii_helper.camera import Camera, CameraDeviceStorageInfo
from quii_helper.camera import api as camera_api
from quii_helper.camera.device_cgi import DeviceCgiEndpoint
from quii_helper.config import AutonomousConfig


def _config() -> AutonomousConfig:
    return AutonomousConfig(
        device_id="device",
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
            "192.0.2.10",
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
