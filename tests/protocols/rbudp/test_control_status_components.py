from quii_helper.protocols.rbudp.control.ack_status import (
    RbUdpControlAckStatus,
)
from quii_helper.protocols.rbudp.control.play_status import (
    RbUdpControlPlayStatus,
)
from quii_helper.protocols.rbudp.control.progress import (
    RbUdpControlProgress,
)
from quii_helper.protocols.rbudp.core.constants import RbUdpProtocolConstants
from quii_helper.protocols.rbudp.core.models import ParsedRbUdpControlPacket
from quii_helper.protocols.rbudp.lanes.registry import RbUdpLane


def _control(
    *,
    local_id: int = 221,
    remote_id: int = 165,
    status_word: int = 0xFFFF0900,
) -> ParsedRbUdpControlPacket:
    return ParsedRbUdpControlPacket(
        marker=0xFFABEFC1,
        word4=0x01000000,
        word8=0x3D000022,
        local_id=local_id,
        remote_id=remote_id,
        status_word=status_word,
        rand16=0,
        packet_len16=28,
    )


def _lane() -> RbUdpLane:
    return {
        "src_id": 0x4000006,
        "word4": 0x3D000022,
        "word8": 0x01000000,
        "local_id": 0,
        "remote_id": 0,
        "flow_sent": False,
        "progress_sent": False,
        "setup_probe_sent": False,
        "play_sync_active": False,
    }


class _Event:
    def __init__(self, value: bool) -> None:
        self.value = value

    def is_set(self) -> bool:
        return self.value

    def set(self) -> None:
        self.value = True


class _Owner(RbUdpProtocolConstants):
    def __init__(self, *, play_sent: bool = True) -> None:
        self._quii_play_sent = _Event(play_sent)
        self.calls: list[tuple[str, tuple, dict]] = []
        self.ack_status = RbUdpControlAckStatus(self)
        self.progress = RbUdpControlProgress(self)
        self.play_status = RbUdpControlPlayStatus(self)

    def _dbg(self, message: str, **kwargs: object) -> None:
        self.calls.append(("dbg", (message,), kwargs))

    def _send_lane_control(
        self,
        lane: RbUdpLane,
        *,
        status_word: int,
        local_id: int | None = None,
        remote_id: int | None = None,
        log_label: str | None = "send_control",
    ) -> None:
        self.calls.append(
            (
                "send_lane_control",
                (lane,),
                {
                    "status_word": status_word,
                    "local_id": local_id,
                    "remote_id": remote_id,
                    "log_label": log_label,
                },
            )
        )

    def _send_wrapped_connect(self, lane: RbUdpLane) -> None:
        self.calls.append(("send_wrapped_connect", (lane,), {}))

    def _start_play_sync(
        self,
        lane: RbUdpLane,
        *,
        local_id: int,
        seed_remote_id: int,
    ) -> None:
        self.calls.append(
            (
                "start_play_sync",
                (lane,),
                {"local_id": local_id, "seed_remote_id": seed_remote_id},
            )
        )


class RbUdpControlStatusComponentTests:
    def test_send_offset_ack_uses_lane_local_id_when_present(self) -> None:
        owner = _Owner()
        lane = _lane()
        lane["local_id"] = 77

        result = owner.ack_status.send_offset_ack(
            lane,
            _control(remote_id=165),
            status_word=owner.CONTROL_POST_CONNECT_ACK_STATUS,
            remote_delta=0x38,
            log_label="post_connect",
        )

        assert (77, 0xDD) == result
        assert 77 == lane["local_id"]
        assert 0xDD == lane["remote_id"]
        assert "send_lane_control" == owner.calls[0][0]
        assert 0xDD == owner.calls[0][2]["remote_id"]

    def test_start_play_sync_from_control_matches_native_biases(self) -> None:
        owner = _Owner()
        lane = _lane()

        owner.progress.start_play_sync_from_control(
            lane,
            _control(local_id=221, remote_id=165),
            reason="test",
        )

        assert "dbg" == owner.calls[0][0]
        assert "start_play_sync" == owner.calls[1][0]
        assert (
            221 + owner.CONTROL_PLAY_SYNC_LOCAL_BIAS
            == owner.calls[1][2]["local_id"]
        )
        assert (
            221 + owner.CONTROL_PLAY_SYNC_STEP
            == owner.calls[1][2]["seed_remote_id"]
        )

    def test_play_sync_status_uses_remote_id_when_present(self) -> None:
        owner = _Owner()
        lane = _lane()

        owner.play_status.handle_play_sync_status(
            lane,
            _control(local_id=100, remote_id=200),
        )

        assert "start_play_sync" == owner.calls[0][0]
        assert 200 == owner.calls[0][2]["local_id"]
        assert (
            100 + owner.CONTROL_PLAY_SYNC_STEP
            == owner.calls[0][2]["seed_remote_id"]
        )
