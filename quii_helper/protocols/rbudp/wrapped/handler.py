from quii_helper.protocols.rbudp.core.models import ParsedRbUdpWrappedPacket
from quii_helper.protocols.rbudp.kcp.link_packets import (
    iter_kcp_packet_frames,
    parse_kcp_packet_frame,
)
from quii_helper.protocols.rbudp.lanes.registry import RbUdpLane
from quii_helper.protocols.rbudp.wrapped.frame_handler import (
    RbUdpWrappedFrameHandlerMixin,
)
from quii_helper.protocols.rbudp.wrapped.lanes import RbUdpWrappedLaneMixin


class RbUdpWrappedHandlerMixin(
    RbUdpWrappedLaneMixin, RbUdpWrappedFrameHandlerMixin
):
    _lane_states: list[RbUdpLane]
    _peer_addr: tuple[str, int]
    _wrapped_debug_seen: set[str]
    dest_id: int | None
    dest_ids: dict[int, int]
    local_id: int
    remote_id: int
    src_id: int
    word4: int
    word8: int

    def _handle_wrapped(self, wrapped: ParsedRbUdpWrappedPacket) -> None:
        self._last_wrapped = wrapped
        self._dbg(
            "recv_wrapped",
            peer=self._peer_addr,
            word4=hex(wrapped.word4),
            word8=hex(wrapped.word8),
            tag=wrapped.tag8,
            inner_len=wrapped.inner_total_length,
            local_id=wrapped.local_id,
            remote_id=wrapped.remote_id,
            status=hex(wrapped.status_word),
        )
        lane = self._lane_for_wrapped(wrapped)
        if lane is not None:
            self._refresh_lane_from_wrapped(lane, wrapped)
        try:
            frames = iter_kcp_packet_frames(wrapped.inner_packet)
        except Exception as exc:
            self._debug_unparsed_wrapped_once(wrapped.inner_packet, exc)
            return

        for frame in frames:
            frame_hex = frame.raw.hex()
            should_debug_inner = frame_hex not in self._wrapped_debug_seen
            if should_debug_inner:
                self._wrapped_debug_seen.add(frame_hex)
            try:
                parsed = parse_kcp_packet_frame(frame)
            except Exception as exc:
                if should_debug_inner:
                    self._dbg(
                        "recv_wrapped_unparsed",
                        error=repr(exc),
                        inner_hex=frame_hex,
                    )
                continue

            self._handle_parsed_wrapped_frame(
                parsed,
                frame_hex=frame_hex,
                should_debug=should_debug_inner,
                wrapped=wrapped,
            )
