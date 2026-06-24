import ipaddress
import random
import socket

from quii_helper.log import logger
from quii_helper.network import udp_target_tuple
from quii_helper.protocols.p2p.models import (
    P2PConnectResponse,
    ParsedP2PTestResponse,
)
from quii_helper.protocols.p2p.targets import iter_p2p_test_targets
from quii_helper.protocols.p2p.test_packets import (
    build_p2p_test_packet,
    parse_p2p_test_response,
)

PROBE_SEQ_BY_KIND = {
    "lan": 0,
    "p2p": 1,
    "trans": 2,
}


def run_udp_probe(
    *,
    sock: socket.socket,
    response: P2PConnectResponse,
    request_session_id: int,
    target_session_flag: str,
    ust_test_address: str,
    timeout: float,
    rng: random.Random,
    attempts_per_target: int = 3,
) -> ParsedP2PTestResponse:
    targets = iter_p2p_test_targets(response, force_trans=0)
    if not targets:
        raise RuntimeError("no p2p test targets in response")

    local_udp_port = sock.getsockname()[1]
    sock.settimeout(timeout)
    best_response: ParsedP2PTestResponse | None = None
    best_rank = -1

    for target in targets:
        logger.debug(
            "[UDPProbe] target kind={} host={}:{} mode={} "
            "local_udp_port={}",
            target.kind,
            target.host,
            target.port,
            target.mode,
            local_udp_port,
        )
        for _attempt in range(attempts_per_target):
            packet = build_p2p_test_packet(
                rb_seq=0,
                probe_seq=PROBE_SEQ_BY_KIND.get(target.kind, 0),
                session_flag=target_session_flag,
                response_session_id=response.response_session_id or 0,
                local_udp_port=local_udp_port,
                target_ip=target.host,
                target_udp_port=target.port,
                test_mode=target.mode,
            )
            sock.sendto(
                packet, udp_target_tuple(sock, target.host, target.port)
            )
            try:
                data, _addr = sock.recvfrom(4096)
            except TimeoutError:
                continue
            parsed = parse_p2p_test_response(data)
            logger.debug(
                "[UDPProbe] response kind={} from={}:{} result={} "
                "status={} test_id={}",
                target.kind,
                parsed.address,
                parsed.port,
                parsed.result_code,
                parsed.status_code,
                parsed.test_id,
            )
            if parsed.ok:
                rank = _rank_probe_response(parsed)
                if best_response is None or rank > best_rank:
                    best_response = parsed
                    best_rank = rank
                if rank >= 3:
                    return parsed
                break
    if best_response is None:
        raise TimeoutError("no successful UDP P2P test response")
    return best_response


def _rank_probe_response(parsed: ParsedP2PTestResponse) -> int:
    try:
        ip = ipaddress.ip_address(parsed.address)
    except ValueError:
        return 0
    if ip.is_private:
        return 3
    if ip.is_loopback:
        return 2
    return 1
