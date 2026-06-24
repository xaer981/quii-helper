from dataclasses import dataclass

from quii_helper.protocols.rbudp.fragments.stream import (
    RbUdpWrappedFragmentStream,
)

FRAGMENT_REMAINDER_MAGIC = b"\xff\xff\xff\xff"


@dataclass(frozen=True)
class RbUdpFragmentGapDecision:
    kind: str
    remainder: bytes = b""
    previous_total_length: int = 0
    tail_start_local_id: int = 0


def decide_fragment_gap_resync(
    stream: RbUdpWrappedFragmentStream,
    *,
    payload: bytes,
    got_local_id: int,
) -> RbUdpFragmentGapDecision:
    inner_end_local_id = stream.inner_end_local_id
    payload_end_local_id = got_local_id + len(payload)

    if got_local_id < inner_end_local_id < payload_end_local_id:
        tail_offset = inner_end_local_id - got_local_id
        return RbUdpFragmentGapDecision(
            kind="tail",
            remainder=payload[tail_offset:],
            previous_total_length=stream.inner_total_length,
            tail_start_local_id=inner_end_local_id,
        )

    if got_local_id >= inner_end_local_id and payload.startswith(
        FRAGMENT_REMAINDER_MAGIC
    ):
        return RbUdpFragmentGapDecision(
            kind="new_packet",
            remainder=payload,
            previous_total_length=got_local_id - stream.start_local_id,
            tail_start_local_id=got_local_id,
        )

    return RbUdpFragmentGapDecision(kind="discard")
