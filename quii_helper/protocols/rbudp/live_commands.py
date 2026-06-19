import queue
import time

from quii_helper.config import RuntimeCredentials
from quii_helper.protocols.quii.live_rb import (
    build_direct_quii_keepalive_rb,
    build_direct_quii_play_oem_rb,
    build_direct_quii_play_rb,
    build_direct_quii_setup_rb,
)
from quii_helper.protocols.quii.url import build_quii_live_path


class RbUdpLiveCommandsMixin:
    def send_quii_setup(self, seq: int = 0) -> None:
        if self.dest_id is None:
            raise RuntimeError("tunnel is not connected")
        for lane, dest_id in self._live_command_lane_destinations():
            src_id = int(lane["src_id"])
            inner = build_direct_quii_setup_rb(
                src_id=src_id, dest_id=dest_id, seq=seq
            )
            self._dbg(
                "send_quii_setup",
                src_id=hex(src_id),
                dest_id=hex(dest_id),
                seq=seq,
                lane_word4=hex(int(lane["word4"])),
                lane_word8=hex(int(lane["word8"])),
            )
            self._send_wrapped(inner, tag8=self.DATA_TAG, lane=lane)

    def send_quii_play(
        self, credentials: RuntimeCredentials, *, seq: int = 1
    ) -> None:
        if self.dest_id is None:
            raise RuntimeError("tunnel is not connected")
        while True:
            try:
                self._data.get_nowait()
            except queue.Empty:
                break
        path = build_quii_live_path(
            channel=self.config.channel,
            stream=self.config.stream,
            ap=2,
            inner=False,
            newcn=False,
            connect_mode=None,
        )
        channel_id = max(0, int(self.config.channel)) & 0xFFFF
        stream_flag = max(0, int(self.config.stream) - 1) & 0xFF
        native_play_profile = {
            "packet_type": 0x01,
            "ext_len_low": channel_id & 0xFF,
            "ext_len_high": (channel_id >> 8) & 0xFF,
            "play_param": 0x01,
            "stream_flag": stream_flag,
        }
        self._quii_play_sent.set()
        self._last_quii_keepalive_at = time.monotonic()
        for index, (lane, dest_id) in enumerate(
            self._live_command_lane_destinations()
        ):
            src_id = int(lane["src_id"])
            profile = native_play_profile
            play_tag = self.QUII_PLAY_TAGS[
                min(index, len(self.QUII_PLAY_TAGS) - 1)
            ]
            play_payload = str(self.config.live_play_payload).lower()
            inner = self._build_quii_play_inner(
                play_payload,
                path=path,
                credentials=credentials,
                src_id=src_id,
                dest_id=dest_id,
                seq=seq,
                profile=profile,
            )
            self._dbg(
                "send_quii_play",
                src_id=hex(src_id),
                dest_id=hex(dest_id),
                seq=seq,
                play_payload=play_payload,
                connect_mode=self.config.connect_mode,
                oem=self.config.oem,
                path=path,
                packet_type=hex(int(profile["packet_type"])),
                idc=channel_id,
                ext_len_low=hex(int(profile["ext_len_low"])),
                ext_len_high=hex(int(profile["ext_len_high"])),
                play_param=hex(int(profile["play_param"])),
                stream_flag=hex(int(profile["stream_flag"])),
                tag8=play_tag.hex(),
                lane_word4=hex(int(lane["word4"])),
                lane_word8=hex(int(lane["word8"])),
                local_id=int(lane["local_id"]),
                remote_id=int(lane["remote_id"]),
                payload_len=len(inner),
                payload_prefix=inner[:48].hex(),
            )
            self._send_wrapped(inner, tag8=play_tag, lane=lane)
            lane["quii_play_end_local_id"] = int(lane["local_id"])
            lane["quii_play_acked"] = False
            lane["quii_next_seq"] = seq + 1

    def maybe_send_quii_keepalive(
        self, credentials: RuntimeCredentials
    ) -> None:
        interval = float(getattr(self.config, "live_keepalive_interval", 10.0))
        if interval <= 0 or not self._quii_play_sent.is_set():
            return
        now = time.monotonic()
        last_sent = float(getattr(self, "_last_quii_keepalive_at", 0.0))
        if not last_sent:
            self._last_quii_keepalive_at = now
            return
        if last_sent and now - last_sent < interval:
            return
        self._last_quii_keepalive_at = now
        self.send_quii_keepalive(credentials)

    def send_quii_keepalive(self, credentials: RuntimeCredentials) -> None:
        if self.dest_id is None:
            raise RuntimeError("tunnel is not connected")
        for lane, dest_id in self._live_command_lane_destinations():
            src_id = int(lane["src_id"])
            seq = int(lane.get("quii_next_seq", 2))
            inner = build_direct_quii_keepalive_rb(
                src_id=src_id,
                dest_id=dest_id,
                seq=seq,
                crypto_mode=2,
                key=credentials.data_encode_key,
                encrypt=True,
            )
            self._dbg(
                "send_quii_keepalive",
                src_id=hex(src_id),
                dest_id=hex(dest_id),
                seq=seq,
                lane_word4=hex(int(lane["word4"])),
                lane_word8=hex(int(lane["word8"])),
                local_id=int(lane["local_id"]),
                remote_id=int(lane["remote_id"]),
                payload_len=len(inner),
                payload_prefix=inner[:48].hex(),
            )
            self._send_wrapped(inner, tag8=self.DATA_TAG, lane=lane)
            lane["quii_next_seq"] = seq + 1

    def _build_quii_play_inner(
        self,
        play_payload: str,
        *,
        path: str,
        credentials: RuntimeCredentials,
        src_id: int,
        dest_id: int,
        seq: int,
        profile: dict[str, int],
    ) -> bytes:
        common = {
            "src_id": src_id,
            "dest_id": dest_id,
            "seq": seq,
            "packet_type": int(profile["packet_type"]),
            "ext_len_low": int(profile["ext_len_low"]),
            "ext_len_high": int(profile["ext_len_high"]),
            "play_param": int(profile["play_param"]),
            "stream_flag": int(profile["stream_flag"]),
            "crypto_mode": 2,
            "key": credentials.data_encode_key,
            "encrypt": True,
        }
        if play_payload == "path":
            return build_direct_quii_play_rb(
                "adminapp",
                credentials.dynamic_password,
                path,
                **common,
            )
        if play_payload == "oem":
            return build_direct_quii_play_oem_rb(
                "adminapp",
                credentials.dynamic_password,
                self.config.oem,
                **common,
            )
        raise ValueError("live_play_payload must be 'path' or 'oem'")

    def wait_quii_setup_ack(self, timeout: float = 3.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            lane_pairs = self._live_command_lane_destinations()
            if lane_pairs and all(
                bool(lane["quii_setup_acked"]) for lane, _dest_id in lane_pairs
            ):
                return True
            remaining = deadline - time.time()
            if remaining <= 0:
                break
            self._quii_setup_acked.wait(min(0.1, remaining))
        return False

    def _live_command_lane_destinations(self) -> list[tuple[dict, int]]:
        pairs = self._connected_lane_destinations()
        active_pairs = [
            (lane, dest_id)
            for lane, dest_id in pairs
            if int(lane["src_id"]) == int(self.src_id)
        ]
        return active_pairs or pairs[:1]
