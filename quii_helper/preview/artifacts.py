from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from quii_helper.io.paths import DATA_DIR
from quii_helper.preview.artifact_paths import PreviewArtifactPaths
from quii_helper.preview.collectors import FragmentPartialCollector
from quii_helper.preview.output_writer import (
    CaptureArtifacts,
    PreviewOutputWriter,
)
from quii_helper.preview.sample_recorder import PreviewJsonlSampleRecorder


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
        self._direct_samples = PreviewJsonlSampleRecorder(
            sample_path=self.direct_blob_sample_path,
            limit=self.direct_blob_sample_limit,
            enabled=self.diagnostics_enabled,
            seen_hashes=self.seen_direct_blob_hashes,
        )
        self._wrapped_tail_samples = PreviewJsonlSampleRecorder(
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
            {
                "msg_index": msg_index,
                "source": source,
                "meta": meta,
                "blob_len": len(blob),
                "blob_hex": blob.hex(),
                "candidates": candidates,
            },
        )

    def save_wrapped_tail_dump(
        self, *, decrypted_tail: bytes, msg_index: int, source: str
    ) -> Path | None:
        if not self.diagnostics_enabled or not decrypted_tail:
            return None
        dump_path = (
            self.wrapped_tail_dump_dir / f"msg_{msg_index:03d}_{source}.bin"
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
            {
                "msg_index": msg_index,
                "source": source,
                "meta": meta,
                "analysis": analysis,
                "blob_len": len(blob),
                "blob_prefix": blob[:128].hex(),
            },
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
