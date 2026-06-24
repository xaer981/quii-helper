from collections.abc import Callable

from quii_helper.protocols.rbudp.fragments.gap import (
    decide_fragment_gap_resync,
)
from quii_helper.protocols.rbudp.fragments.stream import (
    RBUDP_OUTER_HEADER_LEN,
    RbUdpWrappedFragmentStream,
)

DebugCallback = Callable[..., None]


class RbUdpFragmentRemainderCoordinator:
    def __init__(
        self,
        *,
        debug: DebugCallback,
        streams: dict[tuple[int, int], RbUdpWrappedFragmentStream],
    ) -> None:
        self.debug = debug
        self.streams = streams

    def carry_remainder(
        self,
        stream: RbUdpWrappedFragmentStream,
        *,
        remainder: bytes,
        previous_total_length: int,
    ) -> None:
        if not remainder:
            return
        next_start_local_id = stream.start_local_id + previous_total_length
        if len(remainder) < 8 or remainder[:4] != b"\xff\xff\xff\xff":
            self.debug(
                "discard_wrapped_fragment_remainder",
                word4=hex(stream.word4),
                word8=hex(stream.word8),
                start_local_id=next_start_local_id,
                remainder_len=len(remainder),
                prefix=remainder[:32].hex(),
            )
            return
        inner_total_length = int.from_bytes(remainder[4:8], "little")
        if inner_total_length < 0x10:
            self.debug(
                "discard_wrapped_fragment_remainder_bad_length",
                word4=hex(stream.word4),
                word8=hex(stream.word8),
                start_local_id=next_start_local_id,
                inner_total_length=inner_total_length,
                remainder_len=len(remainder),
            )
            return

        carried = RbUdpWrappedFragmentStream.from_remainder(
            stream,
            remainder=remainder,
            previous_total_length=previous_total_length,
            inner_total_length=inner_total_length,
        )
        self.streams[carried.key] = carried
        self.debug(
            "carry_wrapped_fragment_remainder",
            word4=hex(stream.word4),
            word8=hex(stream.word8),
            start_local_id=next_start_local_id,
            have=len(remainder),
            need=inner_total_length,
            next_local_id=carried.next_local_id,
        )

    def resync_gap(
        self,
        stream: RbUdpWrappedFragmentStream,
        *,
        data: bytes,
        got_local_id: int,
        want_local_id: int,
    ) -> bool:
        payload = data[RBUDP_OUTER_HEADER_LEN:]
        inner_end_local_id = stream.inner_end_local_id
        payload_end_local_id = got_local_id + len(payload)
        self.streams.pop(stream.key, None)

        self.debug(
            "wrapped_fragment_stream_gap",
            word4=hex(stream.word4),
            word8=hex(stream.word8),
            got_local_id=got_local_id,
            want_local_id=want_local_id,
            start_local_id=stream.start_local_id,
            inner_end_local_id=inner_end_local_id,
            payload_len=len(payload),
        )

        decision = decide_fragment_gap_resync(
            stream,
            payload=payload,
            got_local_id=got_local_id,
        )

        if decision.kind == "tail":
            self.debug(
                "resync_wrapped_fragment_stream_gap_tail",
                word4=hex(stream.word4),
                word8=hex(stream.word8),
                tail_start_local_id=decision.tail_start_local_id,
                tail_len=len(decision.remainder),
                tail_prefix=decision.remainder[:32].hex(),
            )
            self.carry_remainder(
                stream,
                remainder=decision.remainder,
                previous_total_length=decision.previous_total_length,
            )
            return True

        if decision.kind == "new_packet":
            self.debug(
                "resync_wrapped_fragment_stream_gap_new_packet",
                word4=hex(stream.word4),
                word8=hex(stream.word8),
                start_local_id=decision.tail_start_local_id,
                payload_len=len(decision.remainder),
                payload_prefix=decision.remainder[:32].hex(),
            )
            self.carry_remainder(
                stream,
                remainder=decision.remainder,
                previous_total_length=decision.previous_total_length,
            )
            return True

        self.debug(
            "discard_wrapped_fragment_stream_gap_payload",
            word4=hex(stream.word4),
            word8=hex(stream.word8),
            got_local_id=got_local_id,
            want_local_id=want_local_id,
            inner_end_local_id=inner_end_local_id,
            payload_end_local_id=payload_end_local_id,
            prefix=payload[:32].hex(),
        )
        return True
