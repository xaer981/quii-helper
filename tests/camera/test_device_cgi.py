import pytest

from quii_helper.camera import (
    Camera,
    CameraDeviceProductInfo,
    CameraDeviceScreenFlipInfo,
    CameraDeviceStorageInfo,
    CameraDeviceTimeInfo,
    CameraDeviceTimeTitleInfo,
    CameraDeviceVideoConfigInfo,
    CameraDeviceVideoSwitchInfo,
    CameraDeviceWifiListInfo,
)
from quii_helper.camera import api as camera_api
from quii_helper.camera.device_cgi import DeviceCgiEndpoint
from quii_helper.config import AutonomousConfig
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
            ("wifi", expected_endpoint),
            ("screen", expected_endpoint),
            ("switch", expected_endpoint),
            ("title", expected_endpoint),
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
