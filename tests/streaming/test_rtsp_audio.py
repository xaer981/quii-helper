"""Audio/video share one server but never overwrite each other's transport."""

import socket
from unittest.mock import Mock
from urllib.parse import urljoin

import pytest

from quii_helper.streaming.rtsp import RtspH264Server
from quii_helper.streaming.rtsp.client import RtspClient
from tests.streaming.test_rtp_audio import audio_frame
from tests.streaming.test_rtsp_server import _rtsp_request

IDR = b"\x00\x00\x01\x67sps\x00\x00\x01\x68pps\x00\x00\x01\x65idr"


def test_audio_option_preserves_existing_positional_server_arguments():
    server = RtspH264Server("127.0.0.1", 0, "/live", None, 96, 1200, 123)
    assert server.ssrc == 123 and server.audio is False


def request(sock, reader, method, url, seq, headers=None):
    sock.sendall(_rtsp_request(method, url, seq, headers))
    status = reader.readline()
    response_headers = {}
    while (line := reader.readline()) != b"\r\n":
        if not line:
            raise EOFError
        key, value = line.decode().split(":", 1)
        response_headers[key.lower()] = value.strip()
    body = reader.read(int(response_headers.get("content-length", 0)))
    return status, response_headers, body


def ready(server):
    server.publish(IDR)
    server.publish_audio(audio_frame())


@pytest.mark.parametrize("transport", ["tcp", "udp"])
@pytest.mark.parametrize(
    "path", ["/live", "/live/", "/", "nested/camera/", "/Mixed/Camera/"]
)
def test_both_tracks_keep_independent_transport_and_payloads(transport, path):
    with RtspH264Server(port=0, path=path, audio=True) as server:
        ready(server)
        with socket.create_connection(
            ("127.0.0.1", server.port), timeout=2
        ) as sock:
            sock.settimeout(2)
            with (
                sock.makefile("rb") as reader,
                socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as video,
                socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as audio,
            ):
                video.bind(("127.0.0.1", 0))
                audio.bind(("127.0.0.1", 0))
                video.settimeout(2)
                audio.settimeout(2)
                status, describe_headers, sdp = request(
                    sock, reader, "DESCRIBE", server.url, 1
                )
                assert b"200" in status
                assert b"m=audio 0 RTP/AVP 8" in sdp
                assert (
                    b"PCMA/8000/1" in sdp and b"sprop-parameter-sets=" in sdp
                )
                controls = [
                    line.removeprefix("a=control:")
                    for line in sdp.decode().splitlines()
                    if line.startswith("a=control:trackID=")
                ]
                base = describe_headers["content-base"]
                for track, receiver in [(0, video), (1, audio)]:
                    port = receiver.getsockname()[1]
                    value = (
                        f"RTP/AVP/TCP;interleaved={2 * track}-{2 * track + 1}"
                        if transport == "tcp"
                        else f"RTP/AVP;client_port={port}-{port + 1}"
                    )
                    status, _, _ = request(
                        sock,
                        reader,
                        "SETUP",
                        urljoin(base, controls[track]),
                        track + 2,
                        {"Transport": value},
                    )
                    assert b"200" in status
                status, headers, _ = request(
                    sock, reader, "PLAY", server.url, 4
                )
                assert b"200" in status and "rtp-info" not in headers
                server.publish(IDR)
                server.publish_audio(
                    audio_frame(data=b"a" * 320, milliseconds=40)
                )
                if transport == "tcp":
                    packets = {}
                    for _ in range(4):
                        header = reader.read(4)
                        assert header[:1] == b"$"
                        packets.setdefault(header[1], []).append(
                            reader.read(int.from_bytes(header[2:4], "big"))
                        )
                    video_packets, audio_packets = packets[0], packets[2]
                else:
                    video_packets = [video.recv(2048) for _ in range(3)]
                    audio_packets = [audio.recv(2048)]
                assert all(p[1] & 127 == 96 for p in video_packets)
                assert audio_packets[0][1] & 127 == 8
                assert audio_packets[0][12:] == b"a" * 320
                assert video_packets[0][8:12] != audio_packets[0][8:12]
                request(sock, reader, "TEARDOWN", server.url, 5)


@pytest.mark.parametrize("resume", [False, True])
def test_play_does_not_announce_unknown_first_packet_before_keyframe(resume):
    with RtspH264Server(port=0, audio=True) as server:
        ready(server)
        client = RtspClient(server, Mock(), ("127.0.0.1", 1))
        server._clients.append(client)
        client._handle_request(
            f"SETUP {server.url}/trackID=0 RTSP/1.0\r\nCSeq: 1\r\nTransport: RTP/AVP/TCP"
        )
        if resume:
            client._handle_request(f"PLAY {server.url} RTSP/1.0\r\nCSeq: 2")
            server.publish(IDR)
            client._handle_request(f"PAUSE {server.url} RTSP/1.0\r\nCSeq: 3")
        client._handle_request(f"PLAY {server.url} RTSP/1.0\r\nCSeq: 4")
        response = client.sock.sendall.call_args.args[0]
        assert b"200 OK" in response and b"RTP-Info:" not in response
        for _ in range(3):
            server.publish(b"\x00\x00\x01\x41p")
        assert not client._outgoing
        server.publish(IDR)
        assert len(client._outgoing) == 1


@pytest.mark.parametrize(
    "path", ["/live", "/live/", "/", "nested/camera/", "/Mixed/Camera/"]
)
def test_describe_uses_client_authority_not_loopback_advertisement(path):
    with RtspH264Server(port=0, path=path) as server:
        client = RtspClient(server, Mock(), ("127.0.0.1", 1))
        uri = f"rtsp://192.0.2.10:8554{server.path}?ignored=1"
        try:
            client._handle_request(f"DESCRIBE {uri} RTSP/1.0\r\nCSeq: 1")
            response = client.sock.sendall.call_args.args[0].decode()
            base = next(
                line.split(": ", 1)[1]
                for line in response.splitlines()
                if line.startswith("Content-Base: ")
            )
            assert base.startswith("rtsp://192.0.2.10:8554/")
            assert "?" not in base
            client._handle_request(
                f"SETUP {urljoin(base, 'trackID=0')} RTSP/1.0\r\nCSeq: 2\r\nTransport: RTP/AVP/TCP"
            )
            assert b"200 OK" in client.sock.sendall.call_args.args[0]
        finally:
            client.close()


def test_audio_track_does_not_exist_when_audio_is_disabled():
    with RtspH264Server(port=0) as server:
        with (
            socket.create_connection(
                ("127.0.0.1", server.port), timeout=2
            ) as sock,
            sock.makefile("rb") as reader,
        ):
            status, _, body = request(sock, reader, "DESCRIBE", server.url, 1)
            assert b"200" in status and b"m=audio" not in body
            status, _, _ = request(
                sock,
                reader,
                "SETUP",
                f"{server.url}/trackID=1",
                2,
                {"Transport": "RTP/AVP/TCP;interleaved=2-3"},
            )
            assert b"404" in status


def test_unknown_audio_format_is_rejected_and_disabled_mode_is_unchanged():
    with RtspH264Server(port=0) as disabled:
        disabled.publish_audio(audio_frame(codec=9))
        assert disabled.audio_format is None
    with RtspH264Server(port=0, audio=True) as server:
        with pytest.raises(ValueError, match="requires G.711"):
            server.publish_audio(audio_frame(codec=9))
        server.publish_audio(audio_frame())
        with pytest.raises(ValueError, match="format changed"):
            server.publish_audio(audio_frame(codec=5))


def test_describe_without_audio_returns_retryable_error_not_fake_sdp():
    server = RtspH264Server(audio=True)
    server.audio_ready.wait = Mock(return_value=False)
    client = RtspClient(server, Mock(), ("127.0.0.1", 1))
    client._handle_request(
        "DESCRIBE rtsp://localhost/live RTSP/1.0\r\nCSeq: 1"
    )
    assert b"503 Service Unavailable" in client.sock.sendall.call_args.args[0]
    client.close()


def test_overlapping_interleaved_channels_are_rejected():
    server = RtspH264Server(audio=True)
    client = RtspClient(server, Mock(), ("127.0.0.1", 1))
    from quii_helper.streaming.rtp.g711 import G711Format

    server.audio_format = G711Format(4)
    for track in (0, 1):
        client._handle_request(
            f"SETUP rtsp://localhost/live/trackID={track} RTSP/1.0\r\nCSeq: 1\r\nTransport: RTP/AVP/TCP;interleaved=0-1"
        )
    assert (
        b"461 Unsupported Transport" in client.sock.sendall.call_args.args[0]
    )
    assert client._setup_tracks == {0}
    client.close()


def test_audio_does_not_bypass_shared_queue_budget(monkeypatch):
    from quii_helper.streaming.rtsp import client as module
    from quii_helper.streaming.rtsp.transport import RtpTransport

    monkeypatch.setattr(module, "MAX_QUEUED_RTP_BYTES", 4)
    client = RtspClient(RtspH264Server(audio=True), Mock(), ("127.0.0.1", 1))
    client.tracks[1] = RtpTransport(channel=2)
    client._setup_tracks = {0, 1}
    client.playing = True
    assert client.enqueue_rtp_packets([b"123"], track_id=1)
    assert not client.enqueue_rtp_packets([b"45"], track_id=0)
    client.close()
    assert not client._outgoing and client._outgoing_bytes == 0


def test_late_viewer_receives_audio_but_skips_video_until_keyframe():
    from quii_helper.streaming.rtsp.transport import RtpTransport

    with RtspH264Server(port=0, audio=True) as server:
        client = RtspClient(server, Mock(), ("127.0.0.1", 1))
        client.tracks[1] = RtpTransport(channel=2)
        client._setup_tracks = {0, 1}
        client.playing = True
        server._clients.append(client)
        server.publish(b"\x00\x00\x01\x41p")
        assert not client._outgoing
        server.publish_audio(audio_frame())
        assert len(client._outgoing) == 1
        server.publish(IDR)
        assert len(client._outgoing) == 2
        assert not client._waiting_keyframe


def test_start_prevents_accidental_audio_video_ssrc_collision():
    server = RtspH264Server(port=0, audio=True, ssrc=0)
    server._audio_ssrc = 0
    with server:
        assert server.track_ssrc(0) != server.track_ssrc(1)


def test_native_audio_timestamp_jitter_does_not_create_rtp_gaps():
    import struct

    client = Mock(playing=True)
    client.enqueue_rtp_packets.return_value = True
    with RtspH264Server(port=0, audio=True) as server:
        server._clients.append(client)
        for ms in (0, 22, 87):
            server.publish_audio(audio_frame(milliseconds=ms))
        timestamps = [
            struct.unpack_from("!I", call.args[0][0], 4)[0]
            for call in client.enqueue_rtp_packets.call_args_list
        ]
        assert [
            (b - a) & 0xFFFFFFFF for a, b in zip(timestamps, timestamps[1:])
        ] == [320, 320]
