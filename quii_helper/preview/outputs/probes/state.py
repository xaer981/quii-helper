import hashlib
from pathlib import Path
from typing import Any, Sequence

from quii_helper.io.output_paths import data_base_path
from quii_helper.media.merge.binary import merge_binary_candidates


def probe_output_paths(
    base_name: str | Path,
    probe_name: str,
) -> tuple[Path, Path]:
    base_path = data_base_path(base_name)
    output_path = base_path.with_name(
        f"{base_path.name}_{probe_name}_probe.bin"
    )
    best_path = base_path.with_name(
        f"{base_path.name}_{probe_name}_probe_best.bin"
    )
    return output_path, best_path


def probe_family_prefix(blob: bytes) -> bytes:
    return blob[:16] if len(blob) >= 16 else blob


def merge_persistent_probe_best(
    previous: bytes,
    selected: bytes,
    *,
    replace_disjoint_same_header: bool,
) -> tuple[bytes, str]:
    if not previous:
        return selected, "right_only"

    if replace_disjoint_same_header:
        if len(previous) == len(selected) and previous != selected:
            return selected, "replace_equal_length_current"
        if previous[:8] == selected[:8] and probe_family_prefix(
            previous
        ) != probe_family_prefix(selected):
            return selected, "replace_disjoint_same_header_current"

    _, merged_best, persistent_strategy = merge_binary_candidates(
        [previous, selected]
    )
    return merged_best, persistent_strategy


def probe_summary_payload(
    *,
    unique: Sequence[bytes],
    selected: bytes,
    merge_strategy: str,
    previous: bytes,
    merged_best: bytes,
    persistent_strategy: str,
    analysis: dict[str, Any],
    output_path: Path,
    best_path: Path,
) -> dict[str, Any]:
    return {
        "candidate_count": len(unique),
        "candidate_lens": [len(blob) for blob in unique],
        "merge_strategy": merge_strategy,
        "selected_len": len(selected),
        "selected_sha1": hashlib.sha1(selected).hexdigest(),
        "persistent_previous_len": len(previous),
        "persistent_merge_strategy": persistent_strategy,
        "persistent_len": len(merged_best),
        "persistent_sha1": hashlib.sha1(merged_best).hexdigest(),
        "analysis": analysis,
        "stream_path": str(output_path.resolve()),
        "persistent_path": str(best_path.resolve()),
    }
