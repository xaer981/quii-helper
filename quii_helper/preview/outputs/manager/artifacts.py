from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from quii_helper.io.paths import DATA_DIR
from quii_helper.preview.fragments.collectors import FragmentPartialCollector
from quii_helper.preview.outputs.manager.paths import PreviewArtifactPaths
from quii_helper.preview.outputs.manager.sample_recorder import (
    PreviewJsonlSampleRecorder,
)
from quii_helper.preview.outputs.manager.state import (
    direct_blob_sample_payload,
    sample_recorder,
    should_save_wrapped_tail_dump,
    wrapped_tail_dump_path,
    wrapped_tail_sample_payload,
)
from quii_helper.preview.outputs.writer.output_writer import (
    CaptureArtifacts,
    PreviewOutputWriter,
)


@dataclass
class PreviewArtifactManager:
    diagnostics_enabled: bool = False
    data_dir: Path = DATA_DIR
    direct_blob_sample_limit: int = 16
    wrapped_tail_sample_limit: int = 16
    fragment_partial_sample_limit: int = 16
    seen_direct_blob_hashes: set[str] = field(default_factory=set)
    seen_wrapped_tail_hashes: set[str] = field(default_factory=set)
    _paths: PreviewArtifactPaths = field(init=False, repr=False)
    _direct_samples: PreviewJsonlSampleRecorder = field(init=False, repr=False)
    _wrapped_tail_samples: PreviewJsonlSampleRecorder = field(
        init=False, repr=False
    )

    def __post_init__(self) -> None:
        self._paths = PreviewArtifactPaths(self.data_dir)
        self.data_dir = self._paths.data_dir
        if self.diagnostics_enabled:
            self._paths.prepare_diagnostic_dirs()
        self._direct_samples = sample_recorder(
            sample_path=self.direct_blob_sample_path,
            limit=self.direct_blob_sample_limit,
            enabled=self.diagnostics_enabled,
            seen_hashes=self.seen_direct_blob_hashes,
        )
        self._wrapped_tail_samples = sample_recorder(
            sample_path=self.wrapped_tail_sample_path,
            limit=self.wrapped_tail_sample_limit,
            enabled=self.diagnostics_enabled,
            seen_hashes=self.seen_wrapped_tail_hashes,
        )

    @property
    def direct_blob_sample_path(self) -> Path:
        return self._paths.direct_blob_sample_path

    @property
    def wrapped_tail_sample_path(self) -> Path:
        return self._paths.wrapped_tail_sample_path

    @property
    def fragment_partial_sample_path(self) -> Path:
        return self._paths.fragment_partial_sample_path

    @property
    def wrapped_tail_dump_dir(self) -> Path:
        return self._paths.wrapped_tail_dump_dir

    @property
    def fragment_tail_dump_dir(self) -> Path:
        return self._paths.fragment_tail_dump_dir

    def create_fragment_partial_collector(
        self, *, key: str
    ) -> FragmentPartialCollector:
        return FragmentPartialCollector(
            key=key,
            sample_path=self.fragment_partial_sample_path,
            dump_dir=self.fragment_tail_dump_dir,
            save_diagnostic_artifacts=self.diagnostics_enabled,
            sample_limit=self.fragment_partial_sample_limit,
        )

    def record_direct_blob_sample(
        self,
        *,
        blob: bytes,
        msg_index: int,
        source: str,
        meta: dict[str, Any],
        candidates: list[dict],
    ) -> None:
        self._direct_samples.record(
            blob,
            direct_blob_sample_payload(
                blob=blob,
                msg_index=msg_index,
                source=source,
                meta=meta,
                candidates=candidates,
            ),
        )

    def save_wrapped_tail_dump(
        self, *, decrypted_tail: bytes, msg_index: int, source: str
    ) -> Path | None:
        if not should_save_wrapped_tail_dump(
            diagnostics_enabled=self.diagnostics_enabled,
            decrypted_tail=decrypted_tail,
        ):
            return None
        dump_path = wrapped_tail_dump_path(
            self.wrapped_tail_dump_dir,
            msg_index=msg_index,
            source=source,
        )
        dump_path.write_bytes(decrypted_tail)
        return dump_path

    def record_wrapped_tail_sample(
        self,
        *,
        blob: bytes,
        msg_index: int,
        source: str,
        meta: dict[str, Any],
        analysis: dict,
    ) -> None:
        self._wrapped_tail_samples.record(
            blob,
            wrapped_tail_sample_payload(
                blob=blob,
                msg_index=msg_index,
                source=source,
                meta=meta,
                analysis=analysis,
            ),
        )

    def write_capture_outputs(
        self,
        *,
        decoded_messages: list[dict],
        fragment_partial_collector: FragmentPartialCollector,
        target_duration_seconds: float | None = None,
    ) -> CaptureArtifacts:
        return PreviewOutputWriter(
            diagnostics_enabled=self.diagnostics_enabled,
            data_dir=self.data_dir,
        ).write_capture_outputs(
            decoded_messages=decoded_messages,
            fragment_partial_collector=fragment_partial_collector,
            target_duration_seconds=target_duration_seconds,
        )
