from collections.abc import Callable
from dataclasses import dataclass, field

from quii_helper.media.frames.assembler_state import (
    MEDIA_PACKET_TYPES,
    access_unit_from_frame,
    frame_info_from_parsed_frame,
)
from quii_helper.media.frames.parsing import QuiiCFramePack

AccessUnitSink = Callable[[bytes], None]


@dataclass
class H264LiveAssembler:
    sink: AccessUnitSink | None = None
    packer: QuiiCFramePack = field(default_factory=QuiiCFramePack)
    frame_info: list[dict] = field(default_factory=list)
    access_unit_count: int = 0

    def feed_message(self, decoded: dict) -> list[bytes]:
        header = decoded.get("header")
        if header is None or header.packet_type not in MEDIA_PACKET_TYPES:
            return []

        payload = decoded.get("payload", b"")
        if not isinstance(payload, bytes):
            return []

        access_units = []
        for frame in self.packer.feed(payload):
            self.frame_info.append(frame_info_from_parsed_frame(frame))
            access_unit = access_unit_from_frame(frame)
            if not access_unit:
                continue
            self.access_unit_count += 1
            access_units.append(access_unit)
            if self.sink is not None:
                self.sink(access_unit)
        return access_units

    @property
    def stats(self) -> dict:
        return {
            "frames": len(self.frame_info),
            "access_units": self.access_unit_count,
            "cframe_pack": dict(self.packer.stats),
        }
