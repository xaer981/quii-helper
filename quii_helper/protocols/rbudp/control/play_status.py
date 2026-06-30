from typing import Protocol

from quii_helper.protocols.rbudp.core.models import ParsedRbUdpControlPacket
from quii_helper.protocols.rbudp.lanes.registry import RbUdpLane


class RbUdpControlPlayStatusOwner(Protocol):
    CONTROL_PLAY_SYNC_STEP: int

    def _dbg(self, message: str, **kwargs: object) -> None: ...

    def _start_play_sync(
        self,
        lane: RbUdpLane,
        *,
        local_id: int,
        seed_remote_id: int,
    ) -> None: ...


class RbUdpControlPlayStatus:
    """Handle late play and play-sync control status packets."""

    def __init__(self, owner: RbUdpControlPlayStatusOwner) -> None:
        self._owner = owner

    def handle_play_late_status(
        self, lane: RbUdpLane, control: ParsedRbUdpControlPacket
    ) -> None:
        self._owner._dbg(
            "recv_control_play_late_status",
            src_id=hex(int(lane["src_id"])),
            word4=hex(int(lane["word4"])),
            word8=hex(int(lane["word8"])),
            local_id=control.local_id,
            remote_id=control.remote_id,
        )

    def handle_play_sync_status(
        self, lane: RbUdpLane, control: ParsedRbUdpControlPacket
    ) -> None:
        self._owner._start_play_sync(
            lane,
            local_id=(
                control.remote_id if control.remote_id else control.local_id
            ),
            seed_remote_id=(
                control.local_id + self._owner.CONTROL_PLAY_SYNC_STEP
            )
            & 0xFFFFFFFF,
        )
