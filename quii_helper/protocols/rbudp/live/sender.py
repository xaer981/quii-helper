import queue
import time
from typing import Any, Protocol, cast

from quii_helper.config import RuntimeCredentials
from quii_helper.protocols.quii.live_rb import (
    build_direct_quii_keepalive_rb,
    build_direct_quii_play_oem_rb,
    build_direct_quii_play_rb,
    build_direct_quii_setup_rb,
)
from quii_helper.protocols.quii.url import build_quii_live_path
from quii_helper.protocols.rbudp.lanes.registry import RbUdpLane
from quii_helper.protocols.rbudp.live.command_state import (
    build_native_play_profile,
    build_quii_play_common_args,
    normalize_live_play_payload,
    select_live_command_lane_destinations,
)


class _EventLike(Protocol):
    def is_set(self) -> bool: ...

    def set(self) -> None: ...

    def wait(self, timeout: float | None = None) -> bool: ...


class _QueueLike(Protocol):
    def get_nowait(self) -> object: ...


class _LiveSenderConfig(Protocol):
    channel: int
    connect_mode: int
    live_inner: bool
    live_keepalive_interval: float
    live_newcn: bool
    live_play_payload: str
    oem: str
    stream: int


class _LiveCommandOwner(Protocol):
    DATA_TAG: bytes
    QUII_PLAY_TAGS: tuple[bytes, ...]
    _data: _QueueLike
    _last_quii_keepalive_at: float
    _quii_play_sent: _EventLike
    _quii_setup_acked: _EventLike
    config: _LiveSenderConfig
    dest_id: int | None
    src_id: int

    def _connected_lane_destinations(self) -> list[tuple[RbUdpLane, int]]: ...

    def _dbg(self, message: str, **kwargs: object) -> None: ...

    def _send_wrapped(
        self, inner_packet: bytes, *, tag8: bytes, lane: RbUdpLane
    ) -> None: ...


class RbUdpLiveCommandSender:
    """Sends QUII live commands over an established RBUDP tunnel."""

    def __init__(self, owner: Any) -> None:
        self.owner = cast(_LiveCommandOwner, owner)

    def send_setup(self, seq: int = 0) -> None:
        self._ensure_connected()
        for lane, dest_id in self.lane_destinations():
            src_id = int(lane["src_id"])
            inner = build_direct_quii_setup_rb(
                src_id=src_id, dest_id=dest_id, seq=seq
            )
            self.owner._dbg(
                "send_quii_setup",
                src_id=hex(src_id),
                dest_id=hex(dest_id),
                seq=seq,
                lane_word4=hex(int(lane["word4"])),
                lane_word8=hex(int(lane["word8"])),
            )
            self.owner._send_wrapped(
                inner, tag8=self.owner.DATA_TAG, lane=lane
            )

    def send_play(
        self, credentials: RuntimeCredentials, *, seq: int = 1
    ) -> None:
        self._ensure_connected()
        self._drain_payload_queue()
        path = build_quii_live_path(
            channel=self.owner.config.channel,
            stream=self.owner.config.stream,
            ap=2,
            inner=bool(self.owner.config.live_inner),
            newcn=bool(self.owner.config.live_newcn),
            connect_mode=None,
        )
        native_play_profile = build_native_play_profile(
            channel=self.owner.config.channel,
            stream=self.owner.config.stream,
            inner=bool(self.owner.config.live_inner),
        )
        play_payload = normalize_live_play_payload(
            self.owner.config.live_play_payload
        )
        self.owner._quii_play_sent.set()
        self.owner._last_quii_keepalive_at = time.monotonic()
        for index, (lane, dest_id) in enumerate(self.lane_destinations()):
            src_id = int(lane["src_id"])
            play_tag = self.owner.QUII_PLAY_TAGS[
                min(index, len(self.owner.QUII_PLAY_TAGS) - 1)
            ]
            inner = self.build_play_inner(
                play_payload,
                path=path,
                credentials=credentials,
                src_id=src_id,
                dest_id=dest_id,
                seq=seq,
                profile=native_play_profile,
            )
            self.owner._dbg(
                "send_quii_play",
                src_id=hex(src_id),
                dest_id=hex(dest_id),
                seq=seq,
                play_payload=play_payload,
                connect_mode=self.owner.config.connect_mode,
                oem=self.owner.config.oem,
                path=path,
                packet_type=hex(int(native_play_profile["packet_type"])),
                idc=int(native_play_profile["channel_id"]),
                ext_len_low=hex(int(native_play_profile["ext_len_low"])),
                ext_len_high=hex(int(native_play_profile["ext_len_high"])),
                play_param=hex(int(native_play_profile["play_param"])),
                stream_flag=hex(int(native_play_profile["stream_flag"])),
                inner=bool(native_play_profile["inner"]),
                tag8=play_tag.hex(),
                lane_word4=hex(int(lane["word4"])),
                lane_word8=hex(int(lane["word8"])),
                local_id=int(lane["local_id"]),
                remote_id=int(lane["remote_id"]),
                payload_len=len(inner),
                payload_prefix=inner[:48].hex(),
            )
            self.owner._send_wrapped(inner, tag8=play_tag, lane=lane)
            lane["quii_play_end_local_id"] = int(lane["local_id"])
            lane["quii_play_acked"] = False
            lane["quii_next_seq"] = seq + 1

    def maybe_send_keepalive(self, credentials: RuntimeCredentials) -> None:
        interval = float(
            getattr(self.owner.config, "live_keepalive_interval", 10.0)
        )
        if interval <= 0 or not self.owner._quii_play_sent.is_set():
            return
        now = time.monotonic()
        last_sent = float(getattr(self.owner, "_last_quii_keepalive_at", 0.0))
        if not last_sent:
            self.owner._last_quii_keepalive_at = now
            return
        if now - last_sent < interval:
            return
        self.owner._last_quii_keepalive_at = now
        self.send_keepalive(credentials)

    def send_keepalive(self, credentials: RuntimeCredentials) -> None:
        self._ensure_connected()
        for lane, dest_id in self.lane_destinations():
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
            self.owner._dbg(
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
            self.owner._send_wrapped(
                inner, tag8=self.owner.DATA_TAG, lane=lane
            )
            lane["quii_next_seq"] = seq + 1

    def build_play_inner(
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
        common = build_quii_play_common_args(
            src_id=src_id,
            dest_id=dest_id,
            seq=seq,
            profile=profile,
            data_encode_key=credentials.data_encode_key,
        )
        normalized_payload = normalize_live_play_payload(play_payload)
        if normalized_payload == "path":
            return build_direct_quii_play_rb(
                "adminapp",
                credentials.dynamic_password,
                path,
                **common,
            )
        if normalized_payload == "oem":
            return build_direct_quii_play_oem_rb(
                "adminapp",
                credentials.dynamic_password,
                self.owner.config.oem,
                **common,
            )
        raise AssertionError("unreachable live_play_payload branch")

    def wait_setup_ack(self, timeout: float = 3.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            lane_pairs = self.lane_destinations()
            if lane_pairs and all(
                bool(lane["quii_setup_acked"]) for lane, _dest_id in lane_pairs
            ):
                return True
            remaining = deadline - time.time()
            if remaining <= 0:
                break
            self.owner._quii_setup_acked.wait(min(0.1, remaining))
        return False

    def lane_destinations(self) -> list[tuple[RbUdpLane, int]]:
        return select_live_command_lane_destinations(
            self.owner._connected_lane_destinations(),
            active_src_id=int(self.owner.src_id),
        )

    def _ensure_connected(self) -> None:
        if self.owner.dest_id is None:
            raise RuntimeError("tunnel is not connected")

    def _drain_payload_queue(self) -> None:
        while True:
            try:
                self.owner._data.get_nowait()
            except queue.Empty:
                return
