from collections.abc import Callable
from pathlib import Path

from quii_helper.protocols.quii.live_packets import build_live_setup_packet
from quii_helper.protocols.tcp.live_packet_builder import (
    QuiiLiveOpenPacketBuilder,
)
from quii_helper.protocols.tcp.live_probe_capture import TcpLiveProbeCapture
from quii_helper.protocols.tcp.message_codec import (
    decode_tcp_header,
    decode_tcp_payload,
)
from quii_helper.protocols.tcp.transport import TcpSocketTransport

TcpTransportFactory = Callable[[str, int], TcpSocketTransport]


class QuiiClient:
    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        path: str,
        key: str,
        *,
        use_inner: bool = False,
        transport_factory: TcpTransportFactory = TcpSocketTransport,
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.path = path
        self.key = key or ""
        self.use_inner = use_inner
        self.transport = transport_factory(host, port)
        self.crypto_mode = 0
        self.live_open_builder = QuiiLiveOpenPacketBuilder(
            username=username,
            password=password,
            path=path,
            key=self.key,
            use_inner=use_inner,
        )

    def connect(self, timeout: float = 8.0):
        self.transport.connect(timeout=timeout)

    def close(self):
        self.transport.close()

    def recv_exact(self, size: int) -> bytes:
        return self.transport.recv_exact(size)

    def send_setup(self) -> bytes:
        packet = build_live_setup_packet()
        self.transport.send_all(packet)
        return packet

    def recv_setup(self) -> dict:
        response = self.recv_exact(32)
        status = response[9]
        crypto_mode = response[10]
        self.crypto_mode = crypto_mode if crypto_mode in (0, 1, 2) else 0
        return {
            "raw": response,
            "status": status,
            "crypto_mode": crypto_mode,
        }

    def send_live_open(
        self, play_param: int = 1, stream_flag: int = 0
    ) -> bytes:
        packet = self.build_live_open_packet(
            play_param=play_param, stream_flag=stream_flag
        )
        self.transport.send_all(packet)
        return packet

    def build_live_open_packet(
        self, play_param: int = 1, stream_flag: int = 0
    ) -> bytes:
        return self.live_open_builder.build_live_open_packet(
            crypto_mode=self.crypto_mode,
            play_param=play_param,
            stream_flag=stream_flag,
        )

    def recv_message(self, dump_file: Path | None = None) -> dict:
        header_raw = self.recv_exact(32)
        decoded_header = decode_tcp_header(
            header_raw,
            crypto_mode=self.crypto_mode,
            key=self._key_bytes(),
        )

        payload = b""
        if decoded_header.read_size > 0:
            payload_raw = self.recv_exact(decoded_header.read_size)
            payload = decode_tcp_payload(
                decoded_header,
                payload_raw,
                crypto_mode=self.crypto_mode,
                key=self._key_bytes(),
            )
        else:
            payload_raw = b""

        if dump_file is not None:
            with dump_file.open("ab") as fp:
                fp.write(header_raw)
                fp.write(payload_raw)

        return {
            "header": decoded_header.header,
            "payload": payload,
            "payload_raw": payload_raw,
        }

    def probe_live(
        self, dump_file: Path, *, num_messages: int, play_param: int = 1
    ) -> dict:
        return TcpLiveProbeCapture(
            client=self,
            dump_file=dump_file,
            num_messages=num_messages,
            play_param=play_param,
        ).run()

    def _key_bytes(self) -> bytes:
        return self.live_open_builder.key_bytes(self.crypto_mode)
