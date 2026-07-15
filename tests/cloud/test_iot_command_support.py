from typing import Any

import pytest

from quii_helper.cloud.iot import (
    COMMAND_GET_ALARM_CONFIG,
    COMMAND_GET_FLOODLIGHT_SWITCH,
    COMMAND_GET_RPC_COMMAND_LIST,
    COMMAND_OPEN_LOCK,
    COMMAND_SET_FLOODLIGHT_SWITCH,
    build_iot_control_payload,
    fetch_iot_command_support,
    parse_iot_command_support,
    resolve_iot_service_url,
)
from quii_helper.cloud.oauth import CloudOAuthToken
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


def _credentials(
    *, dynamic_password: str = "device-password"
) -> RuntimeCredentials:
    return RuntimeCredentials(
        session_id="session-id",
        dynamic_password=dynamic_password,
        data_encode_key="data-key",
        auth_code="auth-code",
        transparent_basedata="basedata",
        raw={"login": {}, "token": {}},
    )


class IotCommandSupportTests:
    def test_build_iot_control_payload_matches_native_shape(self) -> None:
        assert {
            "deviceId": "device-1",
            "password": "device-password",
            "command": COMMAND_GET_RPC_COMMAND_LIST,
            "content": {},
        } == build_iot_control_payload(
            "device-1",
            password="device-password",
            command=COMMAND_GET_RPC_COMMAND_LIST,
        )

    def test_parse_command_support_reads_nested_native_payload(self) -> None:
        info = parse_iot_command_support(
            {
                "result": 0,
                "message": "ok",
                "payload": (
                    '{"error":0,"content":{"commandlist":['
                    f'"{COMMAND_OPEN_LOCK}",'
                    f'"{COMMAND_GET_FLOODLIGHT_SWITCH}",'
                    f'"{COMMAND_SET_FLOODLIGHT_SWITCH}",'
                    f'"{COMMAND_GET_ALARM_CONFIG}"'
                    "]}}"
                ),
            }
        )

        assert 0 == info.result
        assert 0 == info.error
        assert (
            COMMAND_OPEN_LOCK,
            COMMAND_GET_FLOODLIGHT_SWITCH,
            COMMAND_SET_FLOODLIGHT_SWITCH,
            COMMAND_GET_ALARM_CONFIG,
        ) == info.commands
        assert 0b01111 == info.support_mask
        assert info.supports_open_lock
        assert info.supports_floodlight_read
        assert info.supports_floodlight_write
        assert info.supports_alarm_config_read
        assert not info.supports_alarm_config_write

    def test_parse_command_support_accepts_direct_payload(self) -> None:
        info = parse_iot_command_support(
            {
                "error": 0,
                "content": {
                    "commandlist": [
                        COMMAND_GET_RPC_COMMAND_LIST,
                        COMMAND_GET_FLOODLIGHT_SWITCH,
                    ]
                },
            }
        )

        assert 0 == info.result
        assert 0 == info.error
        assert (
            COMMAND_GET_RPC_COMMAND_LIST,
            COMMAND_GET_FLOODLIGHT_SWITCH,
        ) == (info.commands)
        assert info.supports_floodlight_read

    def test_parse_command_support_rejects_bad_nested_payload(self) -> None:
        with pytest.raises(QuiiConnectionError, match="payload is not JSON"):
            parse_iot_command_support({"result": 0, "payload": "{"})

    def test_resolve_iot_service_url_prefers_iot_entry(
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
            "quii_helper.cloud.iot.service.query_service_addresses",
            fake_query_service_addresses,
        )

        assert "https://iot.example/api" == resolve_iot_service_url(
            AutonomousConfig()
        )

    def test_resolve_iot_service_url_reports_available_entries(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "quii_helper.cloud.iot.service.query_service_addresses",
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
            resolve_iot_service_url(AutonomousConfig())

    def test_fetch_iot_command_support_uses_cached_runtime_credentials(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[dict[str, Any]] = []

        monkeypatch.setattr(
            "quii_helper.cloud.iot.service.resolve_iot_service_url",
            lambda config: "https://iot.example",
        )
        monkeypatch.setattr(
            "quii_helper.cloud.iot.service.fetch_oauth_access_token",
            lambda config: CloudOAuthToken(
                access_token="access-token",
                refresh_token="refresh-token",
                raw={},
            ),
        )

        def fake_request_iot_command_support(
            base_url: str,
            *,
            token: str,
            device_id: str,
            password: str,
            timeout: float,
            verify_tls: bool,
        ) -> object:
            calls.append(
                {
                    "base_url": base_url,
                    "token": token,
                    "device_id": device_id,
                    "password": password,
                    "timeout": timeout,
                    "verify_tls": verify_tls,
                }
            )
            return object()

        monkeypatch.setattr(
            "quii_helper.cloud.iot.service.request_iot_command_support",
            fake_request_iot_command_support,
        )

        config = AutonomousConfig(device_id="device-1", connect_timeout=3.0)
        result = fetch_iot_command_support(config, credentials=_credentials())

        assert result is not None
        assert {
            "base_url": "https://iot.example",
            "token": "access-token",
            "device_id": "device-1",
            "password": "device-password",
            "timeout": 3.0,
            "verify_tls": config.tls_verify,
        } == calls[0]

    def test_fetch_iot_command_support_propagates_oauth_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fail_oauth(config: AutonomousConfig) -> CloudOAuthToken:
            raise QuiiConnectionError("oauth unavailable")

        monkeypatch.setattr(
            "quii_helper.cloud.iot.service.fetch_oauth_access_token",
            fail_oauth,
        )

        with pytest.raises(QuiiConnectionError, match="oauth unavailable"):
            fetch_iot_command_support(
                AutonomousConfig(),
                credentials=_credentials(),
            )

    def test_fetch_iot_command_support_requires_dynamic_password(self) -> None:
        with pytest.raises(QuiiConnectionError, match="dynamic password"):
            fetch_iot_command_support(
                AutonomousConfig(),
                credentials=_credentials(dynamic_password=""),
            )
