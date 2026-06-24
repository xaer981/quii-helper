from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from quii_helper.io.paths import DATA_DIR, resolve_data_dir
from quii_helper.media.h264.io.writer import write_h264_stream
from quii_helper.preview.fragments.collectors import FragmentPartialCollector
from quii_helper.preview.fragments.embedded_h264 import (
    write_embedded_h264_fallback,
)
from quii_helper.preview.outputs.probes.outputs import (
    write_container_probe_summary,
    write_cpacket_probe_summary,
)
from quii_helper.preview.outputs.writer.state import (
    capture_artifacts,
    resolve_preview_output_base,
    should_write_diagnostic_candidates,
    should_write_embedded_fallback,
)


@dataclass
class CaptureArtifacts:
    media_result: dict | None
    embedded_fallback: dict | None
    container_probe_summary: dict | None
    cpacket_probe_summary: dict | None


@dataclass
class PreviewOutputWriter:
    diagnostics_enabled: bool = False
    data_dir: Path = DATA_DIR
    output_base: str | Path | None = None
    render_snapshot: bool = True
    render_video: bool = True

    def __post_init__(self) -> None:
        self.data_dir = resolve_data_dir(self.data_dir)

    def write_capture_outputs(
        self,
        *,
        decoded_messages: list[dict],
        fragment_partial_collector: FragmentPartialCollector,
        target_duration_seconds: float | None = None,
    ) -> CaptureArtifacts:
        output_base = str(self._resolve_output_base())
        media_result = (
            write_h264_stream(
                output_base,
                decoded_messages,
                render_snapshot=self.render_snapshot,
                render_video=self.render_video,
                target_duration_seconds=target_duration_seconds,
            )
            if decoded_messages
            else None
        )
        container_probe_summary = self._write_container_probe_summary(
            output_base, fragment_partial_collector
        )
        cpacket_probe_summary = self._write_cpacket_probe_summary(
            output_base, fragment_partial_collector
        )
        embedded_fallback = self._write_embedded_fallback(
            output_base,
            media_result=media_result,
            fragment_partial_collector=fragment_partial_collector,
        )
        return capture_artifacts(
            media_result=media_result,
            embedded_fallback=embedded_fallback,
            container_probe_summary=container_probe_summary,
            cpacket_probe_summary=cpacket_probe_summary,
            artifacts_cls=CaptureArtifacts,
        )

    def _resolve_output_base(self) -> Path:
        return resolve_preview_output_base(self.output_base, self.data_dir)

    def _write_container_probe_summary(
        self,
        output_base: str,
        fragment_partial_collector: FragmentPartialCollector,
    ) -> dict | None:
        return self._write_probe_summary(
            output_base,
            fragment_partial_collector.container_probe_candidates,
            write_container_probe_summary,
        )

    def _write_cpacket_probe_summary(
        self,
        output_base: str,
        fragment_partial_collector: FragmentPartialCollector,
    ) -> dict | None:
        return self._write_probe_summary(
            output_base,
            fragment_partial_collector.cpacket_candidates,
            write_cpacket_probe_summary,
        )

    def _write_probe_summary(
        self,
        output_base: str,
        candidates: list[bytes],
        writer: Callable[[str, list[bytes]], dict],
    ) -> dict | None:
        if not should_write_diagnostic_candidates(
            diagnostics_enabled=self.diagnostics_enabled,
            candidates=candidates,
        ):
            return None
        return writer(output_base, candidates)

    def _write_embedded_fallback(
        self,
        output_base: str,
        *,
        media_result: dict | None,
        fragment_partial_collector: FragmentPartialCollector,
    ) -> dict | None:
        if not should_write_embedded_fallback(
            diagnostics_enabled=self.diagnostics_enabled,
            embedded_h264_candidates=(
                fragment_partial_collector.embedded_h264_candidates
            ),
            media_result=media_result,
        ):
            return None
        embedded_fallback = write_embedded_h264_fallback(
            output_base,
            fragment_partial_collector.embedded_h264_candidates,
        )
        if media_result is not None:
            media_result["embedded_fallback"] = embedded_fallback
        return embedded_fallback
