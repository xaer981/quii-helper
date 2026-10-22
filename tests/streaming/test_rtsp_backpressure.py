import threading
import time
from unittest.mock import Mock

import pytest

from quii_helper.streaming.rtsp import RtspH264Server
from quii_helper.streaming.rtsp import client as client_module
from quii_helper.streaming.rtsp.client import RtspClient


def test_slow_client_does_not_block_other_clients_or_producer(monkeypatch):
    monkeypatch.setattr(client_module, "MAX_QUEUED_ACCESS_UNITS", 1)
    server = RtspH264Server()
    server._running = True
    server._started_at = time.monotonic()
    entered, release = threading.Event(), threading.Event()
    slow = RtspClient(server, Mock(), ("127.0.0.1", 1))
    fast = RtspClient(server, Mock(), ("127.0.0.1", 2))
    slow.playing = fast.playing = True
    server._clients = [slow, fast]

    def send(packets, **kwargs):
        entered.set()
        assert release.wait(2)
        return True

    slow.send_rtp_packets = Mock(side_effect=send)
    slow._sender_thread.start()
    try:
        server.publish(b"\x00\x00\x00\x01\x65idr")
        assert entered.wait(1)
        fast._outgoing.clear()
        fast._outgoing_bytes = 0
        server.publish(b"\x00\x00\x00\x01\x41p")
        fast._outgoing.clear()
        fast._outgoing_bytes = 0
        server.publish(b"\x00\x00\x00\x01\x41p")
        assert slow._closed
        assert slow not in server._clients
        assert not fast._closed
        assert len(fast._outgoing) == 1
        assert slow._outgoing_bytes == 0
    finally:
        release.set()
        server.close()
        slow._sender_thread.join(1)


def test_client_byte_budget_counts_inflight_and_pending_packets(monkeypatch):
    monkeypatch.setattr(client_module, "MAX_QUEUED_RTP_BYTES", 4)
    client = RtspClient(RtspH264Server(), Mock(), ("127.0.0.1", 1))
    client.playing = True
    assert client.enqueue_rtp_packets([b"1234"])
    assert not client.enqueue_rtp_packets([b"5"])
    assert client._outgoing_bytes == 4
    client.close()
    assert not client._outgoing and client._outgoing_bytes == 0


@pytest.mark.parametrize("transport", ["tcp", "udp"])
def test_expired_access_unit_is_not_sent(transport):
    client = RtspClient(RtspH264Server(), Mock(), ("127.0.0.1", 1))
    client.transport = transport
    client.udp_rtp_sock = Mock()
    client.udp_rtp_target = ("127.0.0.1", 2)
    assert not client.send_rtp_packets([b"rtp"], deadline=time.monotonic() - 1)
    client.sock.sendall.assert_not_called()
    client.udp_rtp_sock.sendto.assert_not_called()
    client.close()


def test_close_wakes_idle_sender():
    server = RtspH264Server()
    client = RtspClient(server, Mock(), ("127.0.0.1", 1))
    client._sender_thread.start()
    client.close()
    client._sender_thread.join(1)
    assert not client._sender_thread.is_alive()


@pytest.mark.parametrize("transport", ["tcp", "udp"])
def test_slow_trickle_cannot_extend_access_unit_deadline(
    transport, monkeypatch
):
    client = RtspClient(RtspH264Server(), Mock(), ("127.0.0.1", 1))
    client.transport = transport
    client.udp_rtp_sock = Mock()
    client.udp_rtp_target = ("127.0.0.1", 2)
    monkeypatch.setattr(
        client_module.time, "monotonic", Mock(side_effect=[1, 3])
    )
    assert not client.send_rtp_packets([b"one", b"two"], deadline=2)
    sender = (
        client.sock.sendall
        if transport == "tcp"
        else client.udp_rtp_sock.sendto
    )
    assert sender.call_count == 1
    client.close()


def test_close_during_udp_setup_does_not_resurrect_transport(monkeypatch):
    client = RtspClient(RtspH264Server(), Mock(), ("127.0.0.1", 1))
    rtp, rtcp = Mock(), Mock()
    rtp.__enter__ = Mock(return_value=rtp)
    rtp.__exit__ = Mock()
    rtcp.__enter__ = Mock(return_value=rtcp)
    rtcp.__exit__ = Mock()
    rtp.getsockname.return_value = ("127.0.0.1", 8000)
    rtcp.getsockname.return_value = ("127.0.0.1", 8001)
    rtcp.bind.side_effect = lambda address: client.close()
    monkeypatch.setattr(
        client_module.socket, "socket", Mock(side_effect=[rtp, rtcp])
    )
    client._setup_udp_transport(
        Mock(cseq="1"), "RTP/AVP;client_port=6000-6001"
    )
    assert client._closed
    assert client.udp_rtp_sock is None and client.udp_rtcp_sock is None
    rtp.__exit__.assert_called_once()
    rtcp.__exit__.assert_called_once()
    client.sock.sendall.assert_not_called()


def test_pause_discards_pending_media_without_closing_the_client():
    client = RtspClient(RtspH264Server(), Mock(), ("127.0.0.1", 1))
    client.playing = True
    assert client.enqueue_rtp_packets([b"pending"])
    client._handle_request("PAUSE rtsp://localhost/live RTSP/1.0\r\nCSeq: 1")
    assert not client.playing and not client._closed
    assert not client._outgoing and client._outgoing_bytes == 0
    response = client.sock.sendall.call_args.args[0]
    assert response.startswith(b"RTSP/1.0 200 OK")
    assert client.enqueue_rtp_packets([b"raced with PAUSE"])
    assert not client._outgoing
    client.close()
