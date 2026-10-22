import socket
import threading
from unittest.mock import Mock

import pytest

from quii_helper.streaming.rtsp import RtspH264Server
from quii_helper.streaming.rtsp.client import RtspClient
from quii_helper.streaming.rtsp.request import (
    MAX_BODY_BYTES,
    MAX_HEADER_BYTES,
    RtspRequestBuffer,
    parse_request,
)
from quii_helper.streaming.rtsp.transport import (
    client_ports,
    interleaved_channel,
)

OPTIONS = b"OPTIONS rtsp://localhost/live RTSP/1.0\r\nCSeq: 7\r\n\r\n"


def test_requests_and_interleaved_rtcp_can_be_fragmented_and_coalesced():
    buffer = RtspRequestBuffer()
    body = b"\r\n\r\n$NOT A REQUEST"
    first = (
        b"SET_PARAMETER rtsp://localhost/live RTSP/1.0\r\nCSeq: 6\r\nContent-Length: "
        + str(len(body)).encode()
        + b"\r\n\r\n"
    )
    wire = b"$\x01\x00\x08rtcpdata" + first + body + OPTIONS
    requests = []
    for byte in wire:
        requests.extend(buffer.feed(bytes([byte])))
    assert len(requests) == 2
    assert requests[0].encode() == first[:-4]
    assert requests[1].encode() == OPTIONS[:-4]
    assert buffer.pending == b""


@pytest.mark.parametrize(
    "data",
    [
        b"x" * (MAX_HEADER_BYTES + 1),
        OPTIONS.replace(b"CSeq: 7", b"CSeq: nope"),
        OPTIONS.replace(b"CSeq: 7", b"CSeq: 7\r\nContent-Length: -1"),
        OPTIONS.replace(
            b"CSeq: 7", b"CSeq: 7\r\nContent-Length: 1\r\nContent-Length: 1"
        ),
        OPTIONS.replace(
            b"CSeq: 7",
            f"CSeq: 7\r\nContent-Length: {MAX_BODY_BYTES + 1}".encode(),
        ),
        OPTIONS.replace(b"RTSP/1.0", b"HTTP/1.1"),
    ],
)
def test_invalid_or_oversize_request_is_rejected(data):
    with pytest.raises(ValueError):
        RtspRequestBuffer().feed(data)


@pytest.mark.parametrize("value", ["-1-0", "255-256", "0-2", "bad"])
def test_invalid_interleaved_channels_are_rejected(value):
    assert interleaved_channel(f"RTP/AVP/TCP;interleaved={value}") is None


@pytest.mark.parametrize("value", ["-1-2", "0-1", "65536-1", "1-bad"])
def test_invalid_udp_ports_are_rejected(value):
    assert client_ports(f"RTP/AVP;client_port={value}") is None


def test_loopback_client_can_send_rtcp_then_rtsp_on_same_socket():
    with RtspH264Server(port=0) as server:
        assert server.host == "127.0.0.1"
        with socket.create_connection(
            (server.host, server.port), timeout=2
        ) as sock:
            sock.sendall(b"$\x01\x00\x08rtcpdata" + OPTIONS)
            response = sock.recv(4096)
            assert b"200 OK" in response
            assert b"CSeq: 7" in response


def test_bind_failure_closes_listening_socket(monkeypatch):
    sock = Mock()
    sock.bind.side_effect = OSError("occupied")
    monkeypatch.setattr(
        "quii_helper.streaming.rtsp.server.socket.socket", lambda *a: sock
    )
    server = RtspH264Server()
    with pytest.raises(OSError, match="occupied"):
        server.start()
    sock.close.assert_called_once_with()
    assert server._sock is None


def test_incomplete_request_expires_without_trickle_reset(monkeypatch):
    server = RtspH264Server()
    sock = Mock()
    sock.recv.return_value = b"O"
    client = RtspClient(server, sock, ("127.0.0.1", 1))
    server._clients.append(client)
    times = iter([1, 2, 12])
    monkeypatch.setattr(
        "quii_helper.streaming.rtsp.client.time.monotonic", lambda: next(times)
    )
    client._run()
    assert client._closed
    assert sock.recv.call_count == 2


def test_invalid_tcp_setup_returns_461_without_starting_transport():
    client = RtspClient(RtspH264Server(), Mock(), ("127.0.0.1", 1))
    request = parse_request("SETUP rtsp://localhost/live RTSP/1.0\r\nCSeq: 1")
    client._setup_tcp_transport(request, "RTP/AVP/TCP;interleaved=255-256")
    assert (
        b"461 Unsupported Transport" in client.sock.sendall.call_args.args[0]
    )


def test_closed_client_cannot_send_or_reopen_transport():
    client = RtspClient(RtspH264Server(), Mock(), ("127.0.0.1", 1))
    client.close()
    request = parse_request(
        "SETUP rtsp://localhost/live RTSP/1.0\r\nTransport: RTP/AVP/TCP"
    )
    client._handle_setup(request)
    assert client.send_rtp_packets([b"rtp"]) is False
    client.sock.sendall.assert_not_called()


def test_repeated_setup_releases_previous_udp_sockets():
    client = RtspClient(RtspH264Server(), Mock(), ("127.0.0.1", 1))
    rtp, rtcp = Mock(), Mock()
    client.udp_rtp_sock, client.udp_rtcp_sock = rtp, rtcp
    request = parse_request(
        "SETUP rtsp://localhost/live RTSP/1.0\r\nTransport: RTP/AVP/TCP;interleaved=0-1"
    )
    client._handle_setup(request)
    rtp.close.assert_called_once_with()
    rtcp.close.assert_called_once_with()
    assert client.udp_rtp_sock is None


def test_server_rejects_clients_over_limit(monkeypatch):
    monkeypatch.setattr(
        "quii_helper.streaming.rtsp.server.MAX_RTSP_CLIENTS", 0
    )
    with RtspH264Server(port=0) as server:
        with socket.create_connection(
            (server.host, server.port), timeout=2
        ) as sock:
            assert sock.recv(1) == b""
        assert server.client_count == 0


def test_udp_publication_and_close_do_not_race():
    client = RtspClient(RtspH264Server(), Mock(), ("127.0.0.1", 1))
    udp = Mock()
    client.transport = "udp"
    client.udp_rtp_sock = udp
    client.udp_rtp_target = ("127.0.0.1", 1234)
    entered, release, closing, closed = (threading.Event() for _ in range(4))
    errors, results = [], []

    def send(*args):
        entered.set()
        assert release.wait(2)

    def publish():
        try:
            results.append(client.send_rtp_packets([b"one", b"two"]))
        except Exception as exc:
            errors.append(exc)

    def close():
        closing.set()
        client.close()
        closed.set()

    udp.sendto.side_effect = send
    producer = threading.Thread(target=publish)
    closer = threading.Thread(target=close)
    producer.start()
    try:
        assert entered.wait(2)
        closer.start()
        assert closing.wait(2)
        assert closed.wait(1)
    finally:
        release.set()
        producer.join(2)
        if closer.ident is not None:
            closer.join(2)
        client.close()
    assert not errors
    assert results == [False]
    assert closed.is_set()
    udp.close.assert_called_once_with()
