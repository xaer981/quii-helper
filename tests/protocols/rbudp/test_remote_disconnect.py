import queue
import struct
from unittest.mock import Mock

import pytest

from quii_helper import AutonomousConfig
from quii_helper.protocols.p2p.models import (
    P2PConnectResponse,
    ParsedP2PTestResponse,
)
from quii_helper.protocols.rbudp.kcp.connect_packets import (
    build_kcp_disconnect_packet,
)
from quii_helper.protocols.rbudp.receive.loop import RbUdpReceiveLoop
from quii_helper.protocols.rbudp.tunnel.session import RbUdpQuiiTunnel
from quii_helper.support.errors import QuiiConnectionError


def _tunnel_and_packet(*, id_position="dest", flag=0, status=0x1900):
    tunnel = RbUdpQuiiTunnel(
        AutonomousConfig(),
        P2PConnectResponse(),
        ParsedP2PTestResponse(
            result_code=0,
            session_flag="test",
            address="127.0.0.1",
            port=1,
            status_code=0,
            test_id=0,
        ),
        request_session_id=1,
    )
    lane = tunnel._lane_states[0]
    local_id = int(lane["src_id"])
    tunnel.dest_ids[local_id] = 0x12340000
    tunnel.src_id = local_id
    inner = bytearray(
        build_kcp_disconnect_packet(
            src_id=local_id if id_position == "src" else 0x12340000,
            dest_id=local_id if id_position == "dest" else 0x12340000,
        )
    )
    struct.pack_into("<H", inner, 0x12, flag)
    packet = (
        struct.pack(
            "<6I2H",
            0xFFABEFC1,
            int(lane["bootstrap_word8"]),
            0x3D000022,
            1,
            1,
            status,
            0,
            28 + len(inner),
        )
        + inner
    )
    tunnel._udp_sock = Mock()
    received = iter([bytes(packet)])

    def recv(_size):
        try:
            return next(received), ("127.0.0.1", 1)
        except StopIteration:
            tunnel._stop.set()
            raise TimeoutError

    tunnel._udp_sock.recvfrom.side_effect = recv
    return tunnel


@pytest.mark.parametrize("id_position", ["src", "dest"])
@pytest.mark.parametrize("status", [0x1900, 0x0900])
def test_remote_disconnect_reaches_consumer_on_stream_and_legacy_paths(
    id_position, status
):
    tunnel = _tunnel_and_packet(id_position=id_position, status=status)
    tunnel._queue_payload(b"stale", source="test")
    tunnel._receive_loop()
    with pytest.raises(QuiiConnectionError) as error:
        tunnel.recv_packet(timeout=0)
    assert "disconnect" in str(error.value.__cause__.__cause__).lower()
    assert tunnel._stop.is_set()
    tunnel.close()
    assert tunnel._udp_sock is None


@pytest.mark.parametrize("id_position,flag", [("unknown", 0), ("dest", 1)])
def test_unrelated_disconnect_and_response_do_not_terminate_preview(
    id_position, flag
):
    tunnel = _tunnel_and_packet(id_position=id_position, flag=flag)
    RbUdpReceiveLoop(tunnel).run_loop()
    with pytest.raises(queue.Empty):
        tunnel.recv_packet(timeout=0)


def test_disconnect_during_logical_connect_wakes_startup_waiters():
    tunnel = _tunnel_and_packet()
    tunnel.dest_ids.clear()
    tunnel._lane_states[0]["connect_sent"] = True
    tunnel._receive_loop()
    assert tunnel._connected.wait(0)
    assert tunnel._quii_ready.wait(0)
    with pytest.raises(QuiiConnectionError):
        tunnel.recv_packet(timeout=0)


def test_disconnect_for_unsent_connection_does_not_abort_another_lane():
    tunnel = _tunnel_and_packet()
    tunnel.dest_ids.clear()
    RbUdpReceiveLoop(tunnel).run_loop()
    with pytest.raises(queue.Empty):
        tunnel.recv_packet(timeout=0)


@pytest.mark.parametrize("status", [0x1900, 0x0900])
def test_truncated_disconnect_fails_without_reading_missing_ids(status):
    tunnel = _tunnel_and_packet(status=status)
    packet = tunnel._udp_sock.recvfrom(4096)[0]
    packet = bytearray(packet[:-8])
    struct.pack_into("<I", packet, 32, 0x28)
    struct.pack_into("<H", packet, 26, len(packet))
    tunnel._udp_sock.recvfrom.return_value = (bytes(packet), ("127.0.0.1", 1))
    tunnel._udp_sock.recvfrom.side_effect = None
    tunnel._receive_loop()
    with pytest.raises(QuiiConnectionError) as error:
        tunnel.recv_packet(timeout=0)
    assert "truncated KCP disconnect" in str(error.value.__cause__.__cause__)
