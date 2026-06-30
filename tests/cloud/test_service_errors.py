import pytest

from quii_helper.cloud.services.config_apply import apply_discovered_services
from quii_helper.cloud.services.query_parser import (
    parse_service_query_response,
)
from quii_helper.config import (
    AutonomousConfig,
    ServiceEntry,
    ServiceQueryResponse,
)
from quii_helper.support.errors import QuiiConnectionError


def _response(*servers: ServiceEntry) -> ServiceQueryResponse:
    return ServiceQueryResponse(
        seq=1,
        timestamp=0,
        result=0,
        client_region_id=0,
        re_maxtime=0,
        ip_validity=0,
        servers=list(servers),
    )


class CloudServiceErrorsTests:
    def test_query_parser_reports_malformed_response_as_connection_error(
        self,
    ) -> None:
        with pytest.raises(
            QuiiConnectionError, match="unexpected query-hlrv2 response"
        ):
            parse_service_query_response("<response><header /></response>")

    def test_apply_discovered_services_reports_missing_p2papp(self) -> None:
        with pytest.raises(
            QuiiConnectionError, match="query-hlrv2 did not return p2papp"
        ):
            apply_discovered_services(AutonomousConfig(), _response())

    def test_apply_discovered_services_reports_missing_natcheck(self) -> None:
        response = _response(
            ServiceEntry(
                server_type="p2papp",
                query_result=0,
                region_id=1,
                url="https://p2p.example:443",
            )
        )

        with pytest.raises(
            QuiiConnectionError, match="query-hlrv2 did not return natcheck"
        ):
            apply_discovered_services(AutonomousConfig(), response)
