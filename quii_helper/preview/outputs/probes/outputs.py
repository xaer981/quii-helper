from pathlib import Path

from quii_helper.io.safe_read import read_existing_bytes
from quii_helper.media.cpacket.stream import analyze_cpacket_stream
from quii_helper.media.merge.binary import merge_binary_candidates
from quii_helper.media.probes.container import analyze_container_probe
from quii_helper.preview.outputs.probes.state import (
    merge_persistent_probe_best,
    probe_output_paths,
    probe_summary_payload,
)


def write_container_probe_summary(
    base_name: str | Path, probe_blobs: list[bytes]
) -> dict | None:
    unique, selected, strategy = merge_binary_candidates(probe_blobs)
    if not unique:
        return None

    output_path, best_path = probe_output_paths(base_name, "container")
    previous = read_existing_bytes(best_path)
    merged_best, persistent_strategy = merge_persistent_probe_best(
        previous,
        selected,
        replace_disjoint_same_header=True,
    )

    output_path.write_bytes(selected)
    best_path.write_bytes(merged_best)
    analysis = analyze_container_probe(merged_best)
    return probe_summary_payload(
        unique=unique,
        selected=selected,
        merge_strategy=strategy,
        previous=previous,
        merged_best=merged_best,
        persistent_strategy=persistent_strategy,
        analysis=analysis,
        output_path=output_path,
        best_path=best_path,
    )


def write_cpacket_probe_summary(
    base_name: str | Path, cpacket_blobs: list[bytes]
) -> dict | None:
    unique, selected, strategy = merge_binary_candidates(cpacket_blobs)
    if not unique:
        return None

    output_path, best_path = probe_output_paths(base_name, "cpacket")
    previous = read_existing_bytes(best_path)
    merged_best, persistent_strategy = merge_persistent_probe_best(
        previous,
        selected,
        replace_disjoint_same_header=False,
    )

    output_path.write_bytes(selected)
    best_path.write_bytes(merged_best)
    analysis = analyze_cpacket_stream(merged_best)
    return probe_summary_payload(
        unique=unique,
        selected=selected,
        merge_strategy=strategy,
        previous=previous,
        merged_best=merged_best,
        persistent_strategy=persistent_strategy,
        analysis=analysis,
        output_path=output_path,
        best_path=best_path,
    )
