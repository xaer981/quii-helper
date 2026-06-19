from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from quii_helper.io.paths import DATA_DIR
from quii_helper.preview.artifacts import PreviewArtifactManager
from quii_helper.preview.capture_pipeline import PreviewCapturePipeline
from quii_helper.preview.config import (
    DEFAULT_PREVIEW_CAPTURE_SETTINGS,
    PreviewCaptureSettings,
)
from quii_helper.preview.output_writer import PreviewOutputWriter
from quii_helper.preview.packet_processor import PreviewPacketProcessor
from quii_helper.preview.stream import TunnelPacketStream

EmitCallback = Callable[[object], None]


@dataclass
class PreviewPipelineFactory:
    preview_settings: PreviewCaptureSettings = field(
        default_factory=lambda: DEFAULT_PREVIEW_CAPTURE_SETTINGS
    )
    emit: EmitCallback | None = None
    data_dir: Path = DATA_DIR
    render_snapshot: bool = True
    render_video: bool = True

    def create(
        self,
        *,
        tunnel: Any,
        data_key: str,
        credentials: Any | None = None,
        output_base: str | Path | None = None,
    ) -> PreviewCapturePipeline:
        artifacts = self._create_artifacts()
        fragment_partial_collector = (
            artifacts.create_fragment_partial_collector(key=data_key)
        )
        processor = PreviewPacketProcessor(
            key=data_key,
            artifacts=artifacts,
            fragment_partial_collector=fragment_partial_collector,
            emit=self.emit or print,
            min_media_messages=self.preview_settings.min_media_messages,
            max_media_messages=self.preview_settings.max_media_messages,
            direct_blob_summary_limit=(
                self.preview_settings.direct_blob_summary_limit
            ),
        )
        return PreviewCapturePipeline(
            output_writer=self._create_output_writer(
                artifacts, output_base=output_base
            ),
            preview_settings=self.preview_settings,
            processor=processor,
            packet_stream=TunnelPacketStream(tunnel),
            tunnel=tunnel,
            credentials=credentials,
        )

    def _create_artifacts(self) -> PreviewArtifactManager:
        return PreviewArtifactManager(
            diagnostics_enabled=(
                self.preview_settings.save_diagnostic_artifacts
            ),
            data_dir=self.data_dir,
            direct_blob_sample_limit=(
                self.preview_settings.direct_blob_sample_limit
            ),
            wrapped_tail_sample_limit=(
                self.preview_settings.wrapped_tail_sample_limit
            ),
            fragment_partial_sample_limit=(
                self.preview_settings.fragment_partial_sample_limit
            ),
        )

    def _create_output_writer(
        self,
        artifacts: PreviewArtifactManager,
        *,
        output_base: str | Path | None = None,
    ) -> PreviewOutputWriter:
        return PreviewOutputWriter(
            diagnostics_enabled=(
                self.preview_settings.save_diagnostic_artifacts
            ),
            data_dir=artifacts.data_dir,
            output_base=output_base,
            render_snapshot=self.render_snapshot,
            render_video=self.render_video,
        )
