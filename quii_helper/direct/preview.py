import random

from quii_helper.cloud.service_discovery import (
    fetch_runtime_credentials,
    populate_discovered_services,
)
from quii_helper.config import (
    AutonomousConfig,
    RuntimeCredentials,
    validate_camera_app_config,
)
from quii_helper.direct.p2p_session import establish_direct_p2pconnect_session
from quii_helper.direct.peer_selection import (
    log_p2pconnect_response,
    probe_and_select_direct_peers,
)
from quii_helper.log import logger
from quii_helper.network import (
    discover_local_ips,
    discover_public_ip,
    make_dualstack_udp_socket,
)
from quii_helper.protocols.p2p.models import (
    P2PConnectResponse,
    ParsedP2PTestResponse,
)
from quii_helper.protocols.rbudp.tunnel import DirectKcpQuiiTunnel


def open_direct_preview(
    config: AutonomousConfig,
    *,
    credentials: RuntimeCredentials | None = None,
) -> tuple[
    RuntimeCredentials,
    P2PConnectResponse,
    ParsedP2PTestResponse,
    DirectKcpQuiiTunnel,
]:
    validate_camera_app_config(config)
    if not config.ust_address or not config.ust_test_address:
        populate_discovered_services(config)

    credentials = credentials or fetch_runtime_credentials(config)
    rng = random.Random(config.rng_seed)
    public_ip = discover_public_ip()
    local_ips = discover_local_ips()
    logger.debug("[NetInfo] public_ip={} local_ips={}", public_ip, local_ips)
    udp_sock = make_dualstack_udp_socket()
    local_udp_port = udp_sock.getsockname()[1]
    public_udp_port = local_udp_port

    if config.log_peer_diagnostics:
        logger.debug(
            "[P2PDiag] response_candidates_pending {}",
            {
                "local_udp_port": local_udp_port,
                "local_ips": local_ips,
            },
        )

    try:
        p2p_session = establish_direct_p2pconnect_session(
            config=config,
            credentials=credentials,
            rng=rng,
            public_ip=public_ip,
            public_udp_port=public_udp_port,
            local_ips=local_ips,
            local_udp_port=local_udp_port,
        )
    except Exception:
        udp_sock.close()
        raise

    response = p2p_session.response
    request_session_id = p2p_session.request_session_id
    session_flag = p2p_session.session_flag

    if config.log_peer_diagnostics:
        log_p2pconnect_response(response)

    test_response, peer_addr, transport_peer_addr = (
        probe_and_select_direct_peers(
            config=config,
            udp_sock=udp_sock,
            response=response,
            request_session_id=request_session_id,
            session_flag=session_flag,
            rng=rng,
        )
    )
    udp_sock.settimeout(None)

    tunnel = DirectKcpQuiiTunnel(
        config,
        response,
        test_response,
        request_session_id,
        udp_sock=udp_sock,
        peer_addr=peer_addr,
        transport_peer_addr=transport_peer_addr,
        p2p_session_flag=session_flag,
    )
    tunnel.start()
    return credentials, response, test_response, tunnel
