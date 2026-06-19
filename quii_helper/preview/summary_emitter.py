from collections.abc import Callable
from dataclasses import dataclass, field

Emitter = Callable[[object], None]


@dataclass
class PreviewSummaryEmitter:
    emit: Emitter
    direct_blob_summary_limit: int
    state: dict[str, int] = field(default_factory=dict)

    @property
    def implausible_direct_suppressed(self) -> int:
        return self.state.get("implausible_direct_suppressed", 0)

    def emit_packet_summary(
        self, summary: dict, *, source: str, decoded: dict
    ) -> None:
        if source == "direct_quii_blob" and not decoded.get("plausible"):
            self.state["implausible_direct_seen"] = (
                self.state.get("implausible_direct_seen", 0) + 1
            )
            if (
                self.state["implausible_direct_seen"]
                > self.direct_blob_summary_limit
            ):
                self.state["implausible_direct_suppressed"] = (
                    self.state.get("implausible_direct_suppressed", 0) + 1
                )
                return
        self.emit(summary)
