import pytest

from quii_helper.cloud.oauth import (
    OAUTH_SERVICE_TYPES,
    alarm_client_id,
    build_oauth_token_query,
    parse_oauth_token,
    resolve_oauth_service_url,
)
from quii_helper.config import (
    AutonomousConfig,
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


class CloudOAuthTests:
    def test_alarm_client_id_matches_native_format(self) -> None:
        config = AutonomousConfig(
            client_type=32,
            app_id=1234,
            client_id="client-uuid",
        )

        assert "0032-1234-client-uuid" == alarm_client_id(config)

    def test_build_oauth_token_query_matches_native_shape(self) -> None:
        config = AutonomousConfig(
            cloud_account="user@example.com",
            cloud_password="plain-password",
            client_type=32,
            app_id=1234,
            client_id="client-uuid",
            oem="OEM1",
            ip_region_id=8,
        )

        query = build_oauth_token_query(config)

        assert {
            "grant_type": "password",
            "client_id": "0032-1234-client-uuid",
            "client_type": "32",
            "oemid": "OEM1",
            "appid": "1234",
            "usr": "user@example.com",
            "region_id": "8",
            "client_flag": "1",
        } == {key: value for key, value in query.items() if key != "pwd"}
        assert 64 == len(query["pwd"])

    def test_parse_oauth_token_reads_access_token(self) -> None:
        token = parse_oauth_token(
            {
                "access_token": "access",
                "refresh_token": "refresh",
            }
        )

        assert "access" == token.access_token
        assert "refresh" == token.refresh_token

    def test_parse_oauth_token_requires_access_token(self) -> None:
        with pytest.raises(QuiiConnectionError, match="access_token"):
            parse_oauth_token({"code": 403, "message": "denied"})

    def test_resolve_oauth_service_url_prefers_discovery(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fake_query_service_addresses(
            config: AutonomousConfig,
            *,
            server_types: tuple[str, ...],
        ) -> ServiceQueryResponse:
            assert OAUTH_SERVICE_TYPES == server_types
            return _service_response(
                ServiceEntry(
                    server_type="oauth",
                    query_result=0,
                    region_id=1,
                    url="https://oauth.example/",
                    uri="/api",
                )
            )

        monkeypatch.setattr(
            "quii_helper.cloud.oauth.service.query_service_addresses",
            fake_query_service_addresses,
        )

        assert "https://oauth.example/api" == resolve_oauth_service_url(
            AutonomousConfig(auth_url="https://auth.example/userauth")
        )

    def test_resolve_oauth_service_url_falls_back_to_auth_origin(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "quii_helper.cloud.oauth.service.query_service_addresses",
            lambda config, *, server_types: _service_response(
                ServiceEntry(
                    server_type="p2papp",
                    query_result=0,
                    region_id=1,
                    url="https://p2p.example",
                )
            ),
        )

        assert "https://auth.example" == resolve_oauth_service_url(
            AutonomousConfig(auth_url="https://auth.example/userauth")
        )
