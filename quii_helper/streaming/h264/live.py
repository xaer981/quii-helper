from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from quii_helper.media.audio import CameraAudioFrame
from quii_helper.media.frames.assembler_state import (
    KEY_FRAME_TAGS,
    MEDIA_PACKET_TYPES,
    access_unit_from_frame,
    frame_info_from_parsed_frame,
)
from quii_helper.media.frames.parsing import QuiiCFramePack
from quii_helper.models.capture import MediaFrameSummary

AccessUnitSink = Callable[[bytes], None]


@dataclass
class H264LiveAssembler:
    sink: AccessUnitSink | None = None
    packer: QuiiCFramePack = field(default_factory=QuiiCFramePack)
    frame_info: deque[MediaFrameSummary] = field(
        default_factory=lambda: deque(maxlen=128)
    )
    frame_count: int = 0
    access_unit_count: int = 0
    wait_for_keyframe: bool = False
    audio_sink: Callable[[CameraAudioFrame], None] | None = None
    audio_frame_count: int = 0
    frame_sink: Callable[[bytes, dict[str, Any]], None] | None = None

    def feed_message(self, decoded: Mapping[str, Any]) -> list[bytes]:
        header = decoded.get("header")
        if header is None or header.packet_type not in MEDIA_PACKET_TYPES:
            return []

        payload = decoded.get("payload", b"")
        if not isinstance(payload, bytes):
            return []

        access_units = []
        for frame in self.packer.feed(payload):
            if self.audio_sink is not None and frame["frame_tag"] == 0xE3:
                self.audio_sink(CameraAudioFrame.from_cpacket(frame))
                self.audio_frame_count += 1
            if self.wait_for_keyframe:
                if frame["frame_tag"] not in KEY_FRAME_TAGS:
                    continue
                self.wait_for_keyframe = False
            self.frame_count += 1
            self.frame_info.append(frame_info_from_parsed_frame(frame))
            access_unit = access_unit_from_frame(frame)
            if not access_unit:
                continue
            self.access_unit_count += 1
            access_units.append(access_unit)
            if self.frame_sink is not None:
                self.frame_sink(access_unit, frame)
            elif self.sink is not None:
                self.sink(access_unit)
        return access_units

    @property
    def stats(self) -> dict[str, Any]:
        return {
            "frames": self.frame_count,
            "access_units": self.access_unit_count,
            "audio_frames": self.audio_frame_count,
            "cframe_pack": dict(self.packer.stats),
        }
