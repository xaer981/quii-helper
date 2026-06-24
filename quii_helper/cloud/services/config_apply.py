import socket
from urllib.parse import urlparse

from quii_helper.config import AutonomousConfig, ServiceQueryResponse


def apply_discovered_services(
    config: AutonomousConfig, response: ServiceQueryResponse
) -> None:
    p2papp = response.find("p2papp")
    natcheck = response.find("natcheck")
    if p2papp is None or not p2papp.url:
        raise RuntimeError("query-hlrv2 did not return p2papp")
    if natcheck is None or not natcheck.url:
        raise RuntimeError("query-hlrv2 did not return natcheck")

    config.ust_address = (
        f"{p2papp.url}{p2papp.uri}/?{p2papp.param}"
        if p2papp.param
        else f"{p2papp.url}{p2papp.uri}"
    )
    config.ust_test_address = natcheck.url

    parsed = urlparse(p2papp.url)
    if not config.session_flag_server_ip and parsed.hostname:
        config.session_flag_server_ip = socket.gethostbyname(parsed.hostname)
    if config.session_flag_server_port is None:
        config.session_flag_server_port = parsed.port or 0
