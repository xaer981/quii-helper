import socket

from quii_helper.streaming.rtsp import RtspH264Server


def _recv_until(sock: socket.socket, marker: bytes) -> bytes:
    data = b""
    while marker not in data:
        chunk = sock.recv(4096)
        if not chunk:
            break
        data += chunk
    return data


def _rtsp_request(
    method: str, uri: str, cseq: int, headers: dict | None = None
):
    lines = [f"{method} {uri} RTSP/1.0", f"CSeq: {cseq}"]
    for name, value in (headers or {}).items():
        lines.append(f"{name}: {value}")
    return ("\r\n".join(lines) + "\r\n\r\n").encode("ascii")


class RtspH264ServerTests:
    def test_wildcard_bind_url_uses_loopback_connect_host(self) -> None:
        server = RtspH264Server(host="0.0.0.0", port=0).start()
        try:
            assert f"rtsp://127.0.0.1:{server.port}/live" == (server.url)
        finally:
            server.close()

    def test_rtsp_tcp_interleaved_session_receives_published_rtp(
        self,
    ) -> None:
        server = RtspH264Server(host="127.0.0.1", port=0).start()
        try:
            uri = server.url
            with socket.create_connection(("127.0.0.1", server.port)) as sock:
                sock.settimeout(2.0)
                sock.sendall(_rtsp_request("OPTIONS", uri, 1))
                assert b"200 OK" in _recv_until(sock, b"\r\n\r\n")

                sock.sendall(
                    _rtsp_request(
                        "DESCRIBE",
                        uri,
                        2,
                        {"Accept": "application/sdp"},
                    )
                )
                describe = _recv_until(sock, b"a=control:trackID=0\r\n")
                assert b"application/sdp" in describe

                sock.sendall(
                    _rtsp_request(
                        "SETUP",
                        f"{uri}/trackID=0",
                        3,
                        {"Transport": ("RTP/AVP/TCP;unicast;interleaved=2-3")},
                    )
                )
                setup = _recv_until(sock, b"\r\n\r\n")
                assert b"interleaved=2-3" in setup

                sock.sendall(_rtsp_request("PLAY", uri, 4))
                assert b"200 OK" in _recv_until(sock, b"\r\n\r\n")

                server.publish(b"\x00\x00\x00\x01\x65idr")
                frame_header = sock.recv(4)
                assert b"$" == frame_header[:1]
                assert 2 == frame_header[1]
                frame_len = int.from_bytes(frame_header[2:4], "big")
                frame = sock.recv(frame_len)
                assert 0xE0 == frame[1]
                assert b"\x65idr" == frame[12:]
        finally:
            server.close()

    def test_rtsp_udp_session_receives_published_rtp(self) -> None:
        server = RtspH264Server(host="127.0.0.1", port=0).start()
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as rtp_sock:
                rtp_sock.bind(("127.0.0.1", 0))
                rtp_sock.settimeout(2.0)
                client_rtp_port = rtp_sock.getsockname()[1]
                client_rtcp_port = client_rtp_port + 1
                with socket.create_connection(
                    ("127.0.0.1", server.port)
                ) as sock:
                    sock.settimeout(2.0)
                    uri = server.url
                    sock.sendall(
                        _rtsp_request(
                            "SETUP",
                            f"{uri}/trackID=0",
                            1,
                            {
                                "Transport": (
                                    "RTP/AVP;unicast;"
                                    f"client_port={client_rtp_port}-"
                                    f"{client_rtcp_port}"
                                )
                            },
                        )
                    )
                    setup = _recv_until(sock, b"\r\n\r\n")
                    assert b"200 OK" in setup
                    assert b"server_port=" in setup

                    sock.sendall(_rtsp_request("PLAY", uri, 2))
                    assert b"200 OK" in _recv_until(sock, b"\r\n\r\n")

                    server.publish(b"\x00\x00\x00\x01\x65idr")
                    packet, _address = rtp_sock.recvfrom(2048)
                    assert 0xE0 == packet[1]
                    assert b"\x65idr" == packet[12:]
        finally:
            server.close()
