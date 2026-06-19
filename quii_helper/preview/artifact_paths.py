from dataclasses import dataclass
from pathlib import Path

from quii_helper.io.paths import DATA_DIR, resolve_data_dir


@dataclass
class PreviewArtifactPaths:
    data_dir: Path = DATA_DIR

    def __post_init__(self) -> None:
        self.data_dir = resolve_data_dir(self.data_dir)

    @property
    def direct_blob_sample_path(self) -> Path:
        return self.data_dir / "autonomous_direct_blob_samples.jsonl"

    @property
    def wrapped_tail_sample_path(self) -> Path:
        return self.data_dir / "autonomous_wrapped_quii_tail_samples.jsonl"

    @property
    def fragment_partial_sample_path(self) -> Path:
        return self.data_dir / "autonomous_fragment_partial_samples.jsonl"

    @property
    def wrapped_tail_dump_dir(self) -> Path:
        return self.data_dir / "autonomous_wrapped_quii_tail_bins"

    @property
    def fragment_tail_dump_dir(self) -> Path:
        return self.data_dir / "autonomous_fragment_tail_bins"

    def prepare_diagnostic_dirs(self) -> None:
        self.wrapped_tail_dump_dir.mkdir(exist_ok=True)
        self.fragment_tail_dump_dir.mkdir(exist_ok=True)
