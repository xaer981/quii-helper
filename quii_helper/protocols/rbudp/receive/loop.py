from typing import Protocol, cast

from quii_helper.protocols.rbudp.control.packets import (
    parse_rb_udp_control_packet,
)
from quii_helper.protocols.rbudp.core.models import (
    ParsedRbUdpControlPacket,
    ParsedRbUdpWrappedPacket,
)
from quii_helper.protocols.rbudp.receive.incoming_payload import (
    RBUDP_DATA_STATUS_FLAG,
    RBUDP_DIRECT_STATUS,
    RBUDP_MARKER,
    RBUDP_STATUS_MASK,
    RBUDP_STREAM_STATUS,
    RbUdpIncomingPayloadHandler,
    RbUdpIncomingPayloadOwner,
)
from quii_helper.protocols.rbudp.transport.frame_handler import (
    RbUdpTransportFrameHandler,
    RbUdpTransportFrameOwner,
)
from quii_helper.protocols.rbudp.wrapped.packets import (
    parse_rb_udp_wrapped_packet,
)


class _StopEventLike(Protocol):
    def is_set(self) -> bool: ...


class _UdpSocketLike(Protocol):
    def recvfrom(self, bufsize: int) -> tuple[bytes, tuple[str, int]]: ...


class _ReceiveLoopOwner(Protocol):
    _stop: _StopEventLike
    _udp_sock: _UdpSocketLike

    def _dbg(self, message: str, **kwargs: object) -> None: ...

    def _handle_control(self, control: ParsedRbUdpControlPacket) -> None: ...

    def _handle_wrapped(self, wrapped: ParsedRbUdpWrappedPacket) -> None: ...


class RbUdpReceiveLoop:
    """Receive and route UDP packets for an RBUDP tunnel."""

    def __init__(self, owner: _ReceiveLoopOwner) -> None:
        self._owner = owner

    def run_loop(self) -> None:
        owner = self._owner
        incoming_payload = RbUdpIncomingPayloadHandler(
            cast(RbUdpIncomingPayloadOwner, owner)
        )
        transport_frames = RbUdpTransportFrameHandler(
            cast(RbUdpTransportFrameOwner, owner)
        )
        while not owner._stop.is_set():
            try:
                data, _addr = owner._udp_sock.recvfrom(4096)
            except TimeoutError:
                continue
            except OSError:
                break
            if len(data) < 4:
                continue
            marker = int.from_bytes(data[:4], "little")
            if marker == RBUDP_MARKER:
                if len(data) >= 0x1C:
                    status_word = int.from_bytes(data[0x14:0x18], "little")
                    if status_word & RBUDP_DATA_STATUS_FLAG:
                        if incoming_payload.handle_rbudp_data_packet(data):
                            continue
                if len(data) >= 0x20:
                    status_word = int.from_bytes(data[0x14:0x18], "little")
                    inner_marker = int.from_bytes(data[0x1C:0x20], "little")
                    if incoming_payload.maybe_start_wrapped_fragment(
                        data,
                        status_word=status_word,
                        inner_marker=inner_marker,
                    ):
                        continue
                    if inner_marker != 0xFFFFFFFF:
                        status16 = status_word & RBUDP_STATUS_MASK
                        if status16 == RBUDP_STREAM_STATUS:
                            incoming_payload.handle_stream_payload_packet(data)
                            continue
                        if status16 == RBUDP_DIRECT_STATUS:
                            incoming_payload.handle_direct_quii_blob_packet(
                                data
                            )
                            continue
                try:
                    if len(data) == 28:
                        control = parse_rb_udp_control_packet(data)
                        owner._handle_control(control)
                        continue
                    if len(data) != 164:
                        wrapped = parse_rb_udp_wrapped_packet(data)
                        owner._handle_wrapped(wrapped)
                        continue
                except Exception as exc:
                    owner._dbg(
                        "marker_parse_fail",
                        packet_len=len(data),
                        error=repr(exc),
                        prefix=data[:32].hex(),
                    )
            if transport_frames.consume_transport_frame(data):
                continue
            if marker != RBUDP_MARKER:
                continue
            try:
                if len(data) == 28:
                    control = parse_rb_udp_control_packet(data)
                    owner._handle_control(control)
                else:
                    wrapped = parse_rb_udp_wrapped_packet(data)
                    owner._handle_wrapped(wrapped)
            except Exception as exc:
                owner._dbg(
                    "marker_retry_parse_fail",
                    packet_len=len(data),
                    error=repr(exc),
                    prefix=data[:32].hex(),
                )
                continue
