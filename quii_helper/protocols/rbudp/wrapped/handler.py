from typing import Protocol, cast

from quii_helper.protocols.rbudp.core.models import ParsedRbUdpWrappedPacket
from quii_helper.protocols.rbudp.kcp.link_packets import (
    iter_kcp_packet_frames,
    parse_kcp_packet_frame,
)
from quii_helper.protocols.rbudp.wrapped.frame_handler import (
    RbUdpWrappedFrameHandler,
    RbUdpWrappedFrameHandlerOwner,
)
from quii_helper.protocols.rbudp.wrapped.lanes import (
    RbUdpWrappedLaneOwner,
    RbUdpWrappedLaneState,
)


class _WrappedHandlerOwner(Protocol):
    _last_wrapped: ParsedRbUdpWrappedPacket | None
    _peer_addr: tuple[str, int]
    _wrapped_debug_seen: set[str]

    def _dbg(self, message: str, **kwargs: object) -> None: ...


class RbUdpWrappedHandler:
    """Handle RBUDP wrapped packets and dispatch embedded KCP frames."""

    def __init__(self, owner: _WrappedHandlerOwner) -> None:
        self._owner = owner
        self._lane_state = RbUdpWrappedLaneState(
            cast(RbUdpWrappedLaneOwner, owner)
        )
        self._frame_handler = RbUdpWrappedFrameHandler(
            cast(RbUdpWrappedFrameHandlerOwner, owner)
        )

    def handle_wrapped(self, wrapped: ParsedRbUdpWrappedPacket) -> None:
        owner = self._owner
        owner._last_wrapped = wrapped
        owner._dbg(
            "recv_wrapped",
            peer=owner._peer_addr,
            word4=hex(wrapped.word4),
            word8=hex(wrapped.word8),
            tag=wrapped.tag8,
            inner_len=wrapped.inner_total_length,
            local_id=wrapped.local_id,
            remote_id=wrapped.remote_id,
            status=hex(wrapped.status_word),
        )
        lane = self._lane_state.lane_for_wrapped(wrapped)
        if lane is not None:
            self._lane_state.refresh_lane_from_wrapped(lane, wrapped)
        try:
            frames = iter_kcp_packet_frames(wrapped.inner_packet)
        except Exception as exc:
            self._frame_handler.debug_unparsed_wrapped_once(
                wrapped.inner_packet, exc
            )
            return

        for frame in frames:
            frame_hex = frame.raw.hex()
            should_debug_inner = frame_hex not in owner._wrapped_debug_seen
            if should_debug_inner:
                owner._wrapped_debug_seen.add(frame_hex)
            try:
                parsed = parse_kcp_packet_frame(frame)
            except Exception as exc:
                if should_debug_inner:
                    owner._dbg(
                        "recv_wrapped_unparsed",
                        error=repr(exc),
                        inner_hex=frame_hex,
                    )
                continue

            self._frame_handler.handle_parsed_wrapped_frame(
                parsed,
                frame_hex=frame_hex,
                should_debug=should_debug_inner,
                wrapped=wrapped,
            )
