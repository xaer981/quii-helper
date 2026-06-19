import ipaddress

from quii_helper.protocols.p2p.models import P2PConnectResponse, P2PTestTarget


def iter_p2p_test_targets(
    response: P2PConnectResponse,
    *,
    force_trans: int = 0,
    trans_reliable_hint: bool = False,
) -> list[P2PTestTarget]:
    """
    Reproduce the decision tree from P2PTest::OnSendTest(),
    OnSendTestP2P(), and OnSendTestTrans().

    Notes:
    - Native app also performs a LAN probe against `loc-ip/loc-udpport` before
      the public/trans probes. Empirically this is required to ever get LAN
      RB-UDP responses on some peers.
    - `nettype` bit 0 suppresses public P2P probing.
    - `nettype` bit 1 suppresses UTD/trans probing.
    """
    targets: list[P2PTestTarget] = []
    nettype = response.nettype or 0

    for candidate in response.local_ips:
        try:
            ip = ipaddress.ip_address(candidate)
        except ValueError:
            continue
        if ip.is_private and response.local_udp_port:
            targets.append(
                P2PTestTarget(
                    kind="lan",
                    host=candidate,
                    port=int(response.local_udp_port),
                    mode=0,
                    reliable_hint=True,
                )
            )
            break

    if (
        force_trans == 0
        and (nettype & 0x1) == 0
        and response.supports_p2p_test
    ):
        targets.append(
            P2PTestTarget(
                kind="p2p",
                host=response.public_ip or "",
                port=int(response.public_udp_port or 0),
                mode=0,
                reliable_hint=False,
            )
        )

    if (nettype & 0x2) == 0 and response.supports_trans_test:
        targets.append(
            P2PTestTarget(
                kind="trans",
                host=response.utd_public_ip or "",
                port=int(response.utd_public_udp_port or 0),
                mode=1,
                reliable_hint=trans_reliable_hint,
            )
        )

    return targets
