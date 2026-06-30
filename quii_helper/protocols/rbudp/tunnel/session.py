import socket
import threading
from typing import Any, cast

from quii_helper.config import AutonomousConfig, RuntimeCredentials
from quii_helper.protocols.p2p.models import (
    P2PConnectResponse,
    ParsedP2PTestResponse,
)
from quii_helper.protocols.rbudp.control.ack_status import (
    RbUdpControlAckStatus,
    RbUdpControlAckStatusOwner,
)
from quii_helper.protocols.rbudp.control.dispatcher import (
    RbUdpControlDispatcherOwner,
)
from quii_helper.protocols.rbudp.control.flow import (
    RbUdpControlFlow,
    RbUdpControlFlowOwner,
)
from quii_helper.protocols.rbudp.control.handler import (
    RbUdpControlHandler,
)
from quii_helper.protocols.rbudp.control.handshake import (
    RbUdpControlHandshake,
    RbUdpControlHandshakeOwner,
)
from quii_helper.protocols.rbudp.control.lane_updates import (
    RbUdpControlLaneUpdater,
)
from quii_helper.protocols.rbudp.control.play_status import (
    RbUdpControlPlayStatus,
    RbUdpControlPlayStatusOwner,
)
from quii_helper.protocols.rbudp.control.progress import (
    RbUdpControlProgress,
    RbUdpControlProgressOwner,
)
from quii_helper.protocols.rbudp.core.constants import RbUdpProtocolConstants
from quii_helper.protocols.rbudp.core.models import (
    ParsedRbUdpControlPacket,
    ParsedRbUdpWrappedPacket,
)
from quii_helper.protocols.rbudp.fragments.flow import (
    RbUdpWrappedFragmentAssembler,
)
from quii_helper.protocols.rbudp.lanes.control import (
    RbUdpLaneControl,
    RbUdpLaneControlOwner,
)
from quii_helper.protocols.rbudp.lanes.registry import (
    RbUdpLane,
    RbUdpLaneRegistry,
)
from quii_helper.protocols.rbudp.lanes.state import RbUdpLaneState
from quii_helper.protocols.rbudp.live.play_sync import (
    RbUdpPlaySync,
    RbUdpPlaySyncOwner,
)
from quii_helper.protocols.rbudp.live.sender import RbUdpLiveCommandSender
from quii_helper.protocols.rbudp.receive.loop import (
    RbUdpReceiveLoop,
    _ReceiveLoopOwner,
)
from quii_helper.protocols.rbudp.receive.payload_queue import (
    RbUdpPayloadPacket,
    RbUdpPayloadQueue,
)
from quii_helper.protocols.rbudp.receive.stream import (
    RbUdpReceiveStreamAssembler,
)
from quii_helper.protocols.rbudp.transport.io import (
    RbUdpTransportIO,
    RbUdpTransportIOOwner,
)
from quii_helper.protocols.rbudp.tunnel.keepalive import (
    RbUdpKeepalive,
    RbUdpKeepaliveOwner,
)
from quii_helper.protocols.rbudp.tunnel.lifecycle import (
    RbUdpTunnelLifecycle,
    RbUdpTunnelLifecycleOwner,
)
from quii_helper.protocols.rbudp.tunnel.state import (
    build_logical_src_ids,
    initial_direct_data_stats,
    resolve_tunnel_endpoints,
)
from quii_helper.protocols.rbudp.tunnel.threads import RbUdpBackgroundThreads
from quii_helper.protocols.rbudp.wrapped.handler import (
    RbUdpWrappedHandler,
)
from quii_helper.protocols.rbudp.wrapped.sender import (
    RbUdpWrappedSender,
    RbUdpWrappedSenderOwner,
)
from quii_helper.support.log import logger


class RbUdpQuiiTunnel(
    RbUdpProtocolConstants,
):
    def __init__(
        self,
        config: AutonomousConfig,
        response: P2PConnectResponse,
        test_response: ParsedP2PTestResponse,
        request_session_id: int,
        udp_sock: socket.socket | None = None,
        peer_addr: tuple[str, int] | None = None,
        transport_peer_addr: tuple[str, int] | None = None,
        p2p_session_flag: str | None = None,
    ):
        self.config = config
        self.response = response
        self.test_response = test_response
        self.request_session_id = request_session_id
        self.src_ids = build_logical_src_ids(config)
        self.src_id = self.src_ids[0]
        self.dest_id: int | None = None
        self.dest_ids: dict[int, int] = {}
        self._lane_registry = RbUdpLaneRegistry.create(
            src_ids=self.src_ids,
            bootstrap_word4=self.CONTROL_BOOTSTRAP_WORD4,
            bootstrap_remote_id=self.BOOTSTRAP_REMOTE_ID,
            bootstrap_local_ids=self.BOOTSTRAP_LOCAL_IDS,
        )
        self._lane_states: list[RbUdpLane] = self._lane_registry.lanes
        self._lane_state = RbUdpLaneState(
            lane_registry=self._lane_registry,
            src_id=self.src_id,
            src_ids=self.src_ids,
            debug=self._dbg,
        )
        self._connected = threading.Event()
        self._quii_ready = threading.Event()
        self._quii_setup_acked = threading.Event()
        self._quii_play_sent = threading.Event()
        self._stop = threading.Event()
        self._payload_queue = RbUdpPayloadQueue()
        self._data = self._payload_queue.data
        self._udp_sock = udp_sock
        endpoints = resolve_tunnel_endpoints(
            response=response,
            test_response=test_response,
            peer_addr=peer_addr,
            transport_peer_addr=transport_peer_addr,
            p2p_session_flag=p2p_session_flag,
        )
        self._peer_addr = endpoints.peer_addr
        self._transport_peer_addr = endpoints.transport_peer_addr
        self._p2p_session_flag = endpoints.p2p_session_flag
        self.local_id = 0
        self.remote_id = 0
        self.word4 = self.CONTROL_BOOTSTRAP_WORD4
        self.word8 = 0
        self.status_word = self.CONTROL_BOOTSTRAP_STATUS
        self._forced_transition = False
        self._transport_frames_seen = 0
        self._late_bootstrap_pending = 0
        self._late_post_bootstrap_prime = False
        self._threads = RbUdpBackgroundThreads()
        self._last_control: ParsedRbUdpControlPacket | None = None
        self._control_handler = RbUdpControlHandler(
            cast(RbUdpControlDispatcherOwner, self)
        )
        self._receive_loop_runner = RbUdpReceiveLoop(
            cast(_ReceiveLoopOwner, self)
        )
        self._control_handshake = RbUdpControlHandshake(
            cast(RbUdpControlHandshakeOwner, self)
        )
        self._live_command_sender = RbUdpLiveCommandSender(self)
        self._last_wrapped: ParsedRbUdpWrappedPacket | None = None
        self._bootstrap_sent_to: tuple[str, int] | None = None
        self._wrapped_debug_seen: set[str] = set()
        self._wrapped_handler = RbUdpWrappedHandler(self)
        self._wrapped_fragments = RbUdpWrappedFragmentAssembler(
            debug=self._dbg,
            lane_for_packet_words=self._lane_for_packet_words,
            send_fragment_ack=self._send_fragment_ack,
            handle_wrapped=self._handle_wrapped,
            queue_payload=self._queue_payload,
        )
        self._receive_streams = RbUdpReceiveStreamAssembler(
            debug=self._dbg,
            lane_for_packet_words=self._lane_for_packet_words,
            send_fragment_ack=self._send_fragment_ack,
            handle_wrapped=self._handle_wrapped,
        )
        self._lane_control = RbUdpLaneControl(
            cast(RbUdpLaneControlOwner, self)
        )
        self._control_flow = RbUdpControlFlow(
            cast(RbUdpControlFlowOwner, self)
        )
        self._control_lane_updater = RbUdpControlLaneUpdater()
        self._control_ack_status = RbUdpControlAckStatus(
            cast(RbUdpControlAckStatusOwner, self)
        )
        self._control_play_status = RbUdpControlPlayStatus(
            cast(RbUdpControlPlayStatusOwner, self)
        )
        self._control_progress = RbUdpControlProgress(
            cast(RbUdpControlProgressOwner, self)
        )
        self._play_sync = RbUdpPlaySync(cast(RbUdpPlaySyncOwner, self))
        self._direct_data_next_ids: dict[tuple[int, int], int] = {}
        self._direct_data_stats = initial_direct_data_stats()
        self.stream_payload_early_filler_count = 0
        self.stream_payload_early_count = 0
        self.stream_payload_filler_count = 0
        self.stream_payload_count = 0
        self._lifecycle = RbUdpTunnelLifecycle(
            cast(RbUdpTunnelLifecycleOwner, self)
        )
        self._keepalive = RbUdpKeepalive(cast(RbUdpKeepaliveOwner, self))
        self._transport_io = RbUdpTransportIO(
            cast(RbUdpTransportIOOwner, self)
        )
        self._wrapped_sender = RbUdpWrappedSender(
            cast(RbUdpWrappedSenderOwner, self)
        )

    @property
    def peer_addr(self) -> tuple[str, int]:
        return self._transport_io.peer_addr

    @property
    def transport_peer_addr(self) -> tuple[str, int]:
        return self._transport_io.transport_peer_addr

    def start(self) -> None:
        self._lifecycle.start()

    def flush_fragment_partials(self) -> None:
        self._lifecycle.flush_fragment_partials()

    def close(self) -> None:
        self._lifecycle.close()

    def _keepalive_loop(self) -> None:
        self._keepalive.run_loop()

    def _receive_loop(self) -> None:
        self._receive_loop_runner.run_loop()

    def _play_sync_loop(self) -> None:
        self._play_sync.run_loop()

    def _send_udp(self, packet: bytes) -> None:
        self._transport_io.send_udp(packet)

    def _send_transport_udp(
        self, packet: bytes, peer_addr: tuple[str, int] | None = None
    ) -> None:
        self._transport_io.send_transport_udp(packet, peer_addr=peer_addr)

    def _prime_lan_transport(self, *, seq_base: int | None = None) -> None:
        self._transport_io.prime_lan_transport(seq_base=seq_base)

    def send_quii_setup(self, seq: int = 0) -> None:
        self._live_command_sender.send_setup(seq=seq)

    def send_quii_play(
        self, credentials: RuntimeCredentials, *, seq: int = 1
    ) -> None:
        self._live_command_sender.send_play(credentials, seq=seq)

    def maybe_send_quii_keepalive(
        self, credentials: RuntimeCredentials
    ) -> None:
        self._live_command_sender.maybe_send_keepalive(credentials)

    def send_quii_keepalive(self, credentials: RuntimeCredentials) -> None:
        self._live_command_sender.send_keepalive(credentials)

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
        return self._live_command_sender.build_play_inner(
            play_payload,
            path=path,
            credentials=credentials,
            src_id=src_id,
            dest_id=dest_id,
            seq=seq,
            profile=profile,
        )

    def wait_quii_setup_ack(self, timeout: float = 3.0) -> bool:
        return self._live_command_sender.wait_setup_ack(timeout=timeout)

    def _live_command_lane_destinations(
        self,
    ) -> list[tuple[RbUdpLane, int]]:
        return self._live_command_sender.lane_destinations()

    def _send_wrapped(
        self,
        inner_packet: bytes,
        *,
        tag8: bytes,
        lane: RbUdpLane | None = None,
        word4: int | None = None,
        word8: int | None = None,
    ) -> None:
        self._wrapped_sender.send_wrapped(
            inner_packet,
            tag8=tag8,
            lane=lane,
            word4=word4,
            word8=word8,
        )

    def _connected_lane_destinations(self) -> list[tuple[RbUdpLane, int]]:
        return self._wrapped_sender.connected_lane_destinations()

    def _send_wrapped_connect(self, lane: RbUdpLane) -> None:
        self._wrapped_sender.send_wrapped_connect(lane)

    def _send_wrapped_setup_probe(
        self, lane: RbUdpLane, *, connect_id: int, dest_id: int
    ) -> None:
        self._wrapped_sender.send_wrapped_setup_probe(
            lane, connect_id=connect_id, dest_id=dest_id
        )

    def _send_wrapped_data_ack(
        self,
        lane: RbUdpLane,
        *,
        seq: int,
        src_id: int,
        dest_id: int,
        payload_length: int,
        word4: int | None = None,
        word8: int | None = None,
    ) -> None:
        self._wrapped_sender.send_wrapped_data_ack(
            lane,
            seq=seq,
            src_id=src_id,
            dest_id=dest_id,
            payload_length=payload_length,
            word4=word4,
            word8=word8,
        )

    def _send_lane_control(
        self,
        lane: RbUdpLane,
        *,
        status_word: int,
        local_id: int | None = None,
        remote_id: int | None = None,
        word4: int | None = None,
        word8: int | None = None,
        log_label: str | None = "send_control",
        update_lane: bool = True,
        advertise_window: bool = False,
    ) -> None:
        self._lane_control.send_lane_control(
            lane,
            status_word=status_word,
            local_id=local_id,
            remote_id=remote_id,
            word4=word4,
            word8=word8,
            log_label=log_label,
            update_lane=update_lane,
            advertise_window=advertise_window,
        )

    def _native_control_status_word(
        self,
        lane: RbUdpLane,
        status_word: int,
        *,
        buffered: int | None = None,
    ) -> int:
        return self._lane_control.native_control_status_word(
            lane, status_word, buffered=buffered
        )

    def _lane_receive_buffered_bytes(
        self,
        lane: RbUdpLane,
        *,
        word4: int | None = None,
        word8: int | None = None,
    ) -> int:
        return self._lane_control.lane_receive_buffered_bytes(
            lane, word4=word4, word8=word8
        )

    def _send_fragment_ack(
        self,
        lane: RbUdpLane,
        local_id: int,
        remote_id: int,
        *,
        word4: int | None = None,
        word8: int | None = None,
        status_word: int | None = None,
        log_label: str = "send_control_fragment_ack",
    ) -> None:
        self._control_flow.send_fragment_ack(
            lane,
            local_id,
            remote_id,
            word4=word4,
            word8=word8,
            status_word=status_word,
            log_label=log_label,
        )

    def _send_control_bootstrap(self) -> None:
        self._control_flow.send_control_bootstrap()

    def _send_control_established(
        self, lane: RbUdpLane, *, status_word: int | None = None
    ) -> None:
        self._control_flow.send_control_established(
            lane, status_word=status_word
        )

    def _send_pending_established(self) -> None:
        self._control_flow.send_pending_established()

    def _force_initial_established_transition(self) -> None:
        self._control_flow.force_initial_established_transition()

    def _handle_control(self, control: ParsedRbUdpControlPacket) -> None:
        self._control_handler.handle_control(control)

    def _is_quii_play_ack_control(
        self,
        lane: RbUdpLane,
        control: ParsedRbUdpControlPacket,
        *,
        status16: int,
    ) -> bool:
        return self._control_handler.is_quii_play_ack_control(
            lane,
            control,
            status16=status16,
        )

    def _apply_control_lane_ids(
        self, lane: RbUdpLane, control: ParsedRbUdpControlPacket
    ) -> int:
        return self._control_lane_updater.apply_control_lane_ids(lane, control)

    def _send_offset_ack(
        self,
        lane: RbUdpLane,
        control: ParsedRbUdpControlPacket,
        *,
        status_word: int,
        remote_delta: int,
        log_label: str,
    ) -> tuple[int, int]:
        return self._control_ack_status.send_offset_ack(
            lane,
            control,
            status_word=status_word,
            remote_delta=remote_delta,
            log_label=log_label,
        )

    def _handle_play_late_status(
        self, lane: RbUdpLane, control: ParsedRbUdpControlPacket
    ) -> None:
        self._control_play_status.handle_play_late_status(lane, control)

    def _handle_play_sync_status(
        self, lane: RbUdpLane, control: ParsedRbUdpControlPacket
    ) -> None:
        self._control_play_status.handle_play_sync_status(lane, control)

    def _handle_flow_control(
        self,
        lane: RbUdpLane,
        control: ParsedRbUdpControlPacket,
        *,
        peer_logic_id: int,
    ) -> None:
        self._control_progress.handle_flow_control(
            lane, control, peer_logic_id=peer_logic_id
        )

    def _handle_established_control(
        self, lane: RbUdpLane, control: ParsedRbUdpControlPacket
    ) -> None:
        self._control_progress.handle_established_control(lane, control)

    def _start_play_sync_from_control(
        self,
        lane: RbUdpLane,
        control: ParsedRbUdpControlPacket,
        *,
        reason: str,
    ) -> None:
        self._control_progress.start_play_sync_from_control(
            lane, control, reason=reason
        )

    def _handle_progress_control(
        self,
        lane: RbUdpLane,
        control: ParsedRbUdpControlPacket,
        *,
        peer_logic_id: int,
    ) -> None:
        self._control_progress.handle_progress_control(
            lane, control, peer_logic_id=peer_logic_id
        )

    def _handle_syn_ack_control(
        self, control: ParsedRbUdpControlPacket
    ) -> bool:
        return self._control_handshake.handle_syn_ack_control(control)

    def _send_play_sync_ack(
        self, lane: RbUdpLane, *, local_id: int, remote_id: int
    ) -> None:
        self._play_sync.send_play_sync_ack(
            lane, local_id=local_id, remote_id=remote_id
        )

    def _start_play_sync(
        self, lane: RbUdpLane, *, local_id: int, seed_remote_id: int
    ) -> None:
        self._play_sync.start_play_sync(
            lane, local_id=local_id, seed_remote_id=seed_remote_id
        )

    def _advance_play_sync_lane(
        self, lane: RbUdpLane, *, local_id: int, remote_id: int
    ) -> None:
        self._play_sync.advance_play_sync_lane(
            lane, local_id=local_id, remote_id=remote_id
        )

    def _configured_play_sync_iterations(self) -> int:
        return self._play_sync.configured_play_sync_iterations()

    def _is_play_sync_exhausted(self, lane: RbUdpLane) -> bool:
        return self._play_sync.is_play_sync_exhausted(lane)

    def _send_play_data_probe(
        self,
        lane: RbUdpLane,
        *,
        seq: int,
        local_id: int,
        remote_id: int,
        payload: bytes,
    ) -> None:
        self._play_sync.send_play_data_probe(
            lane,
            seq=seq,
            local_id=local_id,
            remote_id=remote_id,
            payload=payload,
        )

    def _maybe_send_play_probe(
        self, lane: RbUdpLane, *, remote_id: int
    ) -> None:
        self._play_sync.maybe_send_play_probe(lane, remote_id=remote_id)

    def _refresh_all_late_lanes_for_probe(self, lane: RbUdpLane) -> None:
        self._play_sync.refresh_all_late_lanes_for_probe(lane)

    def _send_play_stage_ack(
        self,
        lane: RbUdpLane,
        *,
        status_word: int,
        local_id: int,
        remote_id: int,
        log_label: str,
    ) -> None:
        self._play_sync.send_play_stage_ack(
            lane,
            status_word=status_word,
            local_id=local_id,
            remote_id=remote_id,
            log_label=log_label,
        )

    def _maybe_send_play_stage_controls(
        self, lane: RbUdpLane, *, remote_id: int
    ) -> None:
        self._play_sync.maybe_send_play_stage_controls(
            lane, remote_id=remote_id
        )

    def _handle_wrapped(self, wrapped: ParsedRbUdpWrappedPacket) -> None:
        self._wrapped_handler.handle_wrapped(wrapped)

    def _lane_for_packet_words(
        self, *, word4: int, word8: int
    ) -> RbUdpLane | None:
        return self._lane_state.lane_for_packet_words(word4=word4, word8=word8)

    def _next_lane_nonce(self, lane: RbUdpLane) -> int:
        return self._lane_state.next_lane_nonce(lane)

    def _effective_play_sync_remote_id(
        self, lane: RbUdpLane, remote_id: int
    ) -> int:
        return self._lane_state.effective_play_sync_remote_id(lane, remote_id)

    def _refresh_lane_word4(
        self,
        lane: RbUdpLane,
        *,
        target_word4: int | None = None,
        high_delta: int = 0x12,
        low_delta: int = 0x0A,
    ) -> None:
        self._lane_state.refresh_lane_word4(
            lane,
            target_word4=target_word4,
            high_delta=high_delta,
            low_delta=low_delta,
        )

    def _late_family_target_word4(self, lane: RbUdpLane) -> int:
        return self._lane_state.late_family_target_word4(lane)

    def _active_lane(self) -> RbUdpLane:
        return self._lane_state.active_lane()

    def _lane_for_syn_ack(
        self, control: ParsedRbUdpControlPacket
    ) -> RbUdpLane | None:
        return self._lane_state.lane_for_syn_ack(control)

    def _lane_for_control(
        self, control: ParsedRbUdpControlPacket
    ) -> RbUdpLane | None:
        return self._lane_state.lane_for_control(control)

    def _lane_for_src_id(self, src_id: int) -> RbUdpLane | None:
        return self._lane_state.lane_for_src_id(src_id)

    def _queue_payload(
        self, payload: bytes, *, source: str, **meta: Any
    ) -> None:
        self._payload_queue.queue_payload(payload, source=source, **meta)

    def recv_packet(self, timeout: float = 5.0) -> RbUdpPayloadPacket:
        return self._payload_queue.recv_packet(timeout=timeout)

    def recv_payload(self, timeout: float = 5.0) -> bytes:
        return self._payload_queue.recv_payload(timeout=timeout)

    def play_sync_summary(self) -> list[dict[str, object]]:
        return [
            {
                "src_id": hex(int(lane["src_id"])),
                "active": bool(lane["play_sync_active"]),
                "sent": int(lane["play_sync_sent_count"]),
                "remaining": int(lane["play_sync_remaining"]),
            }
            for lane in self._lane_states
        ]

    def fragment_summary(self) -> dict[str, object]:
        return {
            **self._wrapped_fragments.summary(),
            "rbudp_receive_stream": self._receive_streams.summary(),
            "direct_data_acked": self._direct_data_stats["acked"],
            "direct_data_replayed": self._direct_data_stats["replayed"],
            "direct_data_gaps": self._direct_data_stats["gaps"],
        }

    def has_pending_receive_stream_buffers(self) -> bool:
        return self._receive_streams.has_pending()

    def _dbg(self, message: str, **kwargs: Any) -> None:
        if not getattr(self.config, "rbudp_debug", False):
            return
        details = " ".join(f"{key}={value}" for key, value in kwargs.items())
        if details:
            logger.debug("[RbUdp] {} {}", message, details)
        else:
            logger.debug("[RbUdp] {}", message)


DirectKcpQuiiTunnel = RbUdpQuiiTunnel
