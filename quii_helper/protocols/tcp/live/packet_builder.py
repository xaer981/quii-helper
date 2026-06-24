import time
from dataclasses import dataclass

from quii_helper.protocols.quii.live_packets import build_live_play_packet


@dataclass
class QuiiLiveOpenPacketBuilder:
    username: str
    password: str
    path: str
    key: str
    use_inner: bool = False

    def build_live_open_packet(
        self,
        *,
        crypto_mode: int,
        play_param: int = 1,
        stream_flag: int = 0,
        timestamp_ms: int | None = None,
    ) -> bytes:
        _header, _body, packet = build_live_play_packet(
            self.username,
            self.password,
            self.path,
            timestamp_ms=(
                int(time.time() * 1000)
                if timestamp_ms is None
                else timestamp_ms
            ),
            play_param=play_param,
            stream_flag=stream_flag,
            inner=self.use_inner,
            crypto_mode=crypto_mode,
            sha_mode=1,
            key=self.key_bytes(crypto_mode) if crypto_mode else None,
            encrypt=crypto_mode != 0,
        )
        return packet

    def key_bytes(self, crypto_mode: int) -> bytes:
        if crypto_mode == 1:
            return self.key.encode("utf-8")[:16].ljust(16, b"\x00")
        if crypto_mode == 2:
            return self.key.encode("utf-8")[:32].ljust(32, b"\x00")
        return b""
