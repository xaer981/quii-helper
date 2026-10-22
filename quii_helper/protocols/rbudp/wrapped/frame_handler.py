from collections import deque
from hashlib import sha256
from typing import Any, Protocol, cast

from quii_helper.protocols.rbudp.core.models import (
    ParsedKcpConnectResponse,
    ParsedPacketDispatch,
    ParsedRbDataPacket,
    ParsedRbUdpWrappedPacket,
)
from quii_helper.protocols.rbudp.lanes.registry import RbUdpLane
from quii_helper.support.errors import QuiiConnectionError

MAX_WRAPPED_DEBUG_SAMPLES = 128


class _EventLike(Protocol):
    def set(self) -> None: ...


class RbUdpWrappedFrameHandlerOwner(Protocol):
    _connected: _EventLike
    _quii_setup_acked: _EventLike
    dest_id: int | None
    dest_ids: dict[int, int]
    local_id: int
    remote_id: int
    src_id: int
    word4: int
    word8: int

    def _dbg(self, message: str, **kwargs: object) -> None: ...

    def _lane_for_src_id(self, src_id: int) -> RbUdpLane | None: ...

    def _queue_payload(
        self, payload: bytes, *, source: str, **meta: Any
    ) -> None: ...

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
    ) -> None: ...

    def _send_wrapped_setup_probe(
        self, lane: RbUdpLane, *, connect_id: int, dest_id: int
    ) -> None: ...


class RbUdpWrappedFrameHandler:
    """Handle parsed frames embedded in RBUDP wrapped packets."""

    def __init__(self, owner: RbUdpWrappedFrameHandlerOwner) -> None:
        self._owner = owner
        self._debug_seen: deque[bytes] = deque(
            maxlen=MAX_WRAPPED_DEBUG_SAMPLES
        )

    def should_debug_frame(self, packet: bytes) -> bool:
        """Deduplicate recent diagnostics without retaining media payloads."""
        if not getattr(
            getattr(self._owner, "config", None), "rbudp_debug", False
        ):
            return False
        fingerprint = sha256(packet).digest()
        if fingerprint in self._debug_seen:
            return False
        self._debug_seen.append(fingerprint)
        return True

    def handle_parsed_wrapped_frame(
        self,
        parsed: ParsedPacketDispatch,
        *,
        frame_hex: str,
        should_debug: bool,
        wrapped: ParsedRbUdpWrappedPacket,
    ) -> None:
        self.debug_parsed_frame(
            parsed, frame_hex=frame_hex, should_debug=should_debug
        )

        if parsed.disconnect is not None:
            packet = parsed.disconnect.raw
            if int.from_bytes(packet[0x12:0x14], "little") != 0:
                return
            if len(packet) < 0x30:
                raise QuiiConnectionError("truncated KCP disconnect packet")
            # Native OnP2PRequDisconect looks up both IDs in the connection map.
            for offset in (0x2C, 0x28):
                connection_id = int.from_bytes(
                    packet[offset : offset + 4], "little"
                )
                lane = self._owner._lane_for_src_id(connection_id)
                if lane is not None and (
                    connection_id in self._owner.dest_ids
                    or lane["connect_sent"]
                ):
                    raise QuiiConnectionError(
                        "camera disconnected KCP preview connection"
                    )
            return

        if parsed.connect is not None:
            self.handle_connect_frame(parsed.connect)
            return

        if (
            parsed.data is not None
            and not parsed.data.is_ack
            and parsed.data.payload
        ):
            self.handle_data_frame(parsed.data, wrapped=wrapped)
            return

        if (
            parsed.data is not None
            and parsed.data.is_ack
            and parsed.data.seq == 0
        ):
            self.handle_setup_ack_frame(parsed.data)

    def handle_data_frame(
        self, data: ParsedRbDataPacket, *, wrapped: ParsedRbUdpWrappedPacket
    ) -> None:
        owner = self._owner
        # Native KcpLinkClient::OnP2PRequData does not ACK inbound data frames.
        # Reliability is handled by the outer RBUDP receive stream ACK.
        owner._queue_payload(
            data.payload,
            source="wrapped_quii",
            packet_type_flag=data.packet_type_flag,
            command=data.command,
            seq=data.seq,
            dest_id=data.dest_id,
            src_id=data.src_id,
        )

    def ack_data_frame(
        self, data: ParsedRbDataPacket, *, wrapped: ParsedRbUdpWrappedPacket
    ) -> None:
        owner = self._owner
        lane = owner._lane_for_src_id(data.dest_id)
        if lane is None:
            owner._dbg(
                "skip_quii_data_ack_no_lane",
                seq=hex(data.seq),
                dest_id=hex(data.dest_id),
                src_id=hex(data.src_id),
            )
            return
        owner._send_wrapped_data_ack(
            lane,
            seq=data.seq,
            src_id=data.dest_id,
            dest_id=data.src_id,
            payload_length=data.body_length_field,
            word4=wrapped.word8,
            word8=wrapped.word4,
        )

    def handle_setup_ack_frame(self, data: ParsedRbDataPacket) -> None:
        owner = self._owner
        ack_lane = owner._lane_for_src_id(data.dest_id)
        if ack_lane is not None:
            ack_lane["quii_setup_acked"] = True
        owner._dbg(
            "recv_quii_setup_ack",
            seq=hex(data.seq),
            dest_id=hex(data.dest_id),
            src_id=hex(data.src_id),
        )
        owner._quii_setup_acked.set()

    def debug_unparsed_wrapped_once(
        self, inner_packet: bytes, exc: Exception
    ) -> None:
        if not self.should_debug_frame(inner_packet):
            return
        self._owner._dbg(
            "recv_wrapped_unparsed",
            error=repr(exc),
            inner_hex=inner_packet.hex(),
        )

    def debug_parsed_frame(
        self,
        parsed: ParsedPacketDispatch,
        *,
        frame_hex: str,
        should_debug: bool,
    ) -> None:
        if not should_debug:
            return
        owner = self._owner
        if parsed.connect is not None:
            owner._dbg(
                "recv_wrapped_connect_parsed",
                packet_type=parsed.connect.packet_type_flag,
                result_code=parsed.connect.result_code,
                command=hex(parsed.connect.command),
                payload_length=parsed.connect.payload_length,
                connect_id=hex(parsed.connect.connect_id),
                dest_id=hex(parsed.connect.dest_id),
                ok=parsed.connect.ok,
                inner_hex=frame_hex,
            )
        elif parsed.data is not None:
            owner._dbg(
                "recv_wrapped_data_parsed",
                packet_type=parsed.data.packet_type_flag,
                command=hex(parsed.data.command),
                seq=hex(parsed.data.seq),
                payload_length=parsed.data.payload_length,
                dest_id=hex(parsed.data.dest_id),
                src_id=hex(parsed.data.src_id),
                inner_hex=frame_hex,
            )

    def handle_connect_frame(self, connect: ParsedKcpConnectResponse) -> None:
        owner = self._owner
        connect_lane = owner._lane_for_src_id(connect.connect_id)
        if connect_lane is None:
            return
        if connect.packet_type_flag != 1:
            return
        if connect.connect_id != int(connect_lane["src_id"]):
            return
        if connect.dest_id == 0:
            return
        owner.dest_ids[connect.connect_id] = connect.dest_id
        if owner.dest_id is None:
            owner.src_id = connect.connect_id
            owner.dest_id = connect.dest_id
            owner.word4 = int(connect_lane["word4"])
            owner.word8 = int(connect_lane["word8"])
            owner.local_id = int(connect_lane["local_id"])
            owner.remote_id = int(connect_lane["remote_id"])
        if not bool(connect_lane["setup_probe_sent"]):
            owner._send_wrapped_setup_probe(
                connect_lane,
                connect_id=connect.connect_id,
                dest_id=connect.dest_id,
            )
        owner._dbg(
            "connect_ok",
            connect_id=hex(connect.connect_id),
            dest_id=hex(connect.dest_id),
            active_src_id=hex(owner.src_id),
        )
        owner._connected.set()
