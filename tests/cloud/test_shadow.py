from typing import Any

import pytest

from quii_helper.cloud.oauth import CloudOAuthToken
from quii_helper.cloud.shadow import (
    SHADOW_FIELD_DEVICE_STATE,
    build_shadow_status_payload,
    fetch_device_shadow_info,
    parse_device_shadow_info,
    resolve_shadow_service_url,
)
from quii_helper.config import (
    AutonomousConfig,
    RuntimeCredentials,
    ServiceEntry,
    ServiceQueryResponse,
)
from quii_helper.support.errors import QuiiConnectionError


def _service_response(*entries: ServiceEntry) -> ServiceQueryResponse:
    return ServiceQueryResponse(
        seq=1,
        timestamp=0,
        result=0,
        client_region_id=1,
        re_maxtime=0,
        ip_validity=0,
        servers=list(entries),
    )


def _credentials() -> RuntimeCredentials:
    return RuntimeCredentials(
        session_id="session-id",
        dynamic_password="dynamic-password",
        data_encode_key="data-key",
        auth_code="auth-code",
        transparent_basedata="basedata",
        raw={"login": {}, "token": {}},
    )


class CloudShadowTests:
    def test_build_shadow_status_payload_matches_native_field_info(
        self,
    ) -> None:
        assert {
            "thingId": "device-1",
            "fieldNames": [SHADOW_FIELD_DEVICE_STATE],
        } == build_shadow_status_payload("device-1")

    def test_parse_device_shadow_info_reads_native_fields(self) -> None:
        info = parse_device_shadow_info(
            {
                "code": 0,
                "data": {
                    "thingId": "device-1",
                    "fields": {
                        "Device_state": {
                            "F1_state": 1,
                            "Switch_state": {
                                "channel": 2,
                                "index": 3,
                                "state": 4,
                                "type": 5,
                            },
                            "Private_mode_state": 6,
                        }
                    },
                },
                "errTip": "",
                "msg": "ok",
                "path": "/openapi-tdk/device/status",
                "timestamp": 123,
            }
        )

        assert 0 == info.code
        assert "device-1" == info.thing_id
        assert info.device_state is not None
        assert 1 == info.device_state.f1_state
        assert 6 == info.device_state.private_mode_state
        assert info.device_state.switch_state is not None
        assert 2 == info.device_state.switch_state.channel
        assert 3 == info.device_state.switch_state.index
        assert 4 == info.device_state.switch_state.state
        assert 5 == info.device_state.switch_state.type

    def test_resolve_shadow_service_url_prefers_iot_entry(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fake_query_service_addresses(
            config: AutonomousConfig,
            *,
            server_types: tuple[str, ...],
        ) -> ServiceQueryResponse:
            assert ("iot", "openapi", "shadow") == server_types
            return _service_response(
                ServiceEntry(
                    server_type="iot",
                    query_result=0,
                    region_id=1,
                    url="https://iot.example/",
                    uri="/api",
                )
            )

        monkeypatch.setattr(
            "quii_helper.cloud.shadow.service.query_service_addresses",
            fake_query_service_addresses,
        )

        assert "https://iot.example/api" == resolve_shadow_service_url(
            AutonomousConfig()
        )

    def test_resolve_shadow_service_url_reports_available_entries(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "quii_helper.cloud.shadow.service.query_service_addresses",
            lambda config, *, server_types: _service_response(
                ServiceEntry(
                    server_type="p2papp",
                    query_result=0,
                    region_id=1,
                    url="https://p2p.example",
                )
            ),
        )

        with pytest.raises(QuiiConnectionError, match="available: p2papp"):
            resolve_shadow_service_url(AutonomousConfig())

    def test_fetch_device_shadow_info_uses_cached_runtime_credentials(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[dict[str, Any]] = []

        monkeypatch.setattr(
            "quii_helper.cloud.shadow.service.resolve_shadow_service_url",
            lambda config: "https://iot.example",
        )
        monkeypatch.setattr(
            "quii_helper.cloud.shadow.service.fetch_oauth_access_token",
            lambda config: CloudOAuthToken(
                access_token="access-token",
                refresh_token="refresh-token",
                raw={},
            ),
        )

        def fake_request_device_shadow_info(
            base_url: str,
            *,
            token: str,
            thing_id: str,
            timeout: float,
            verify_tls: bool,
        ) -> object:
            calls.append(
                {
                    "base_url": base_url,
                    "token": token,
                    "thing_id": thing_id,
                    "timeout": timeout,
                    "verify_tls": verify_tls,
                }
            )
            return object()

        monkeypatch.setattr(
            "quii_helper.cloud.shadow.service.request_device_shadow_info",
            fake_request_device_shadow_info,
        )

        config = AutonomousConfig(device_id="device-1", connect_timeout=3.0)
        result = fetch_device_shadow_info(config, credentials=_credentials())

        assert result is not None
        assert {
            "base_url": "https://iot.example",
            "token": "access-token",
            "thing_id": "device-1",
            "timeout": 3.0,
            "verify_tls": config.tls_verify,
        } == calls[0]

    def test_fetch_device_shadow_info_propagates_oauth_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fail_oauth(config: AutonomousConfig) -> CloudOAuthToken:
            raise QuiiConnectionError("oauth unavailable")

        monkeypatch.setattr(
            "quii_helper.cloud.shadow.service.fetch_oauth_access_token",
            fail_oauth,
        )

        with pytest.raises(QuiiConnectionError, match="oauth unavailable"):
            fetch_device_shadow_info(
                AutonomousConfig(), credentials=_credentials()
            )
