import hashlib
from pathlib import Path

from quii_helper.io.output_paths import data_base_path
from quii_helper.media.binary_merge import merge_binary_candidates
from quii_helper.media.container_probe_analysis import analyze_container_probe
from quii_helper.media.cpacket_stream import analyze_cpacket_stream


def write_container_probe_summary(
    base_name: str | Path, probe_blobs: list[bytes]
) -> dict | None:
    unique, selected, strategy = merge_binary_candidates(probe_blobs)
    if not unique:
        return None

    base_path = data_base_path(base_name)
    output_path = base_path.with_name(f"{base_path.name}_container_probe.bin")
    best_path = base_path.with_name(
        f"{base_path.name}_container_probe_best.bin"
    )
    previous = _read_existing(best_path)

    def probe_family_prefix(blob: bytes) -> bytes:
        return blob[:16] if len(blob) >= 16 else blob

    if previous:
        if len(previous) == len(selected) and previous != selected:
            merged_best = selected
            persistent_strategy = "replace_equal_length_current"
        elif previous[:8] == selected[:8] and probe_family_prefix(
            previous
        ) != probe_family_prefix(selected):
            merged_best = selected
            persistent_strategy = "replace_disjoint_same_header_current"
        else:
            _, merged_best, persistent_strategy = merge_binary_candidates(
                [previous, selected]
            )
    else:
        merged_best = selected
        persistent_strategy = "right_only"

    output_path.write_bytes(selected)
    best_path.write_bytes(merged_best)
    analysis = analyze_container_probe(merged_best)
    return {
        "candidate_count": len(unique),
        "candidate_lens": [len(blob) for blob in unique],
        "merge_strategy": strategy,
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


def write_cpacket_probe_summary(
    base_name: str | Path, cpacket_blobs: list[bytes]
) -> dict | None:
    unique, selected, strategy = merge_binary_candidates(cpacket_blobs)
    if not unique:
        return None

    base_path = data_base_path(base_name)
    output_path = base_path.with_name(f"{base_path.name}_cpacket_probe.bin")
    best_path = base_path.with_name(f"{base_path.name}_cpacket_probe_best.bin")
    previous = _read_existing(best_path)

    if previous:
        _, merged_best, persistent_strategy = merge_binary_candidates(
            [previous, selected]
        )
    else:
        merged_best = selected
        persistent_strategy = "right_only"

    output_path.write_bytes(selected)
    best_path.write_bytes(merged_best)
    analysis = analyze_cpacket_stream(merged_best)
    return {
        "candidate_count": len(unique),
        "candidate_lens": [len(blob) for blob in unique],
        "merge_strategy": strategy,
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


def _read_existing(path: Path) -> bytes:
    if not path.exists():
        return b""
    try:
        return path.read_bytes()
    except Exception:
        return b""
