from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, TypeVar, cast

from quii_helper.io.paths import resolve_data_dir, timestamped_output_base

ArtifactT = TypeVar("ArtifactT")


def capture_artifacts(
    *,
    media_result: object | None,
    embedded_fallback: object | None,
    container_probe_summary: dict[str, Any] | None,
    cpacket_probe_summary: dict[str, Any] | None,
    artifacts_cls: Callable[..., ArtifactT],
) -> ArtifactT:
    return artifacts_cls(
        media_result=media_result,
        embedded_fallback=embedded_fallback,
        container_probe_summary=container_probe_summary,
        cpacket_probe_summary=cpacket_probe_summary,
    )


def resolve_preview_output_base(
    output_base: str | Path | None,
    data_dir: str | Path,
) -> Path:
    if output_base is None:
        return timestamped_output_base(Path(data_dir))
    output_path = Path(output_base)
    if output_path.suffix:
        output_path = output_path.with_suffix("")
    return resolve_data_dir(output_path.parent) / output_path.name


def should_write_diagnostic_candidates(
    *, diagnostics_enabled: bool, candidates: Sequence[bytes]
) -> bool:
    return bool(diagnostics_enabled and candidates)


def media_result_has_assembled_units(
    media_result: Mapping[str, Any] | None,
) -> bool:
    if media_result is None:
        return False
    summary = media_result.get("summary", {})
    if not isinstance(summary, Mapping):
        return False
    return cast(object, summary.get("assembled_units", 0)) != 0


def should_write_embedded_fallback(
    *,
    diagnostics_enabled: bool,
    embedded_h264_candidates: Sequence[bytes],
    media_result: Mapping[str, Any] | None,
) -> bool:
    if not should_write_diagnostic_candidates(
        diagnostics_enabled=diagnostics_enabled,
        candidates=embedded_h264_candidates,
    ):
        return False
    return not media_result_has_assembled_units(media_result)
