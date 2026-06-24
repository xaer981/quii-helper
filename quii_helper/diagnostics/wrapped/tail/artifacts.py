from pathlib import Path

from quii_helper.diagnostics.wrapped.tail.candidate_extractors import (
    candidate_cpacket_from_decrypted_tail,
)
from quii_helper.diagnostics.wrapped.tail.candidate_state import (
    TAIL_ARTIFACT_CONTAINER_PROBE,
    TAIL_ARTIFACT_H264_FROM_STARTCODE,
    tail_startcode_artifact_candidate,
)
from quii_helper.diagnostics.wrapped.tail.crypto import (
    decrypt_wrapped_quii_tail_bytes,
)
from quii_helper.diagnostics.wrapped.tail.probe import CONTAINER_PROBE_MARKER
from quii_helper.io.paths import resolve_data_dir


def dump_partial_tail_artifacts(
    *,
    blob: bytes,
    key: str,
    decoded: dict,
    dump_dir: Path,
    stem: str,
) -> dict[str, str]:
    artifacts: dict[str, str] = {}
    decrypted_tail = decrypt_wrapped_quii_tail_bytes(blob, key, decoded)
    if not decrypted_tail:
        return artifacts

    dump_dir = resolve_data_dir(dump_dir)
    tail_path = dump_dir / f"{stem}_tail_decrypted.bin"
    tail_path.write_bytes(decrypted_tail)
    artifacts["decrypted_tail_path"] = str(tail_path)

    cpacket_blob = candidate_cpacket_from_decrypted_tail(decrypted_tail)
    if cpacket_blob:
        cpacket_path = dump_dir / f"{stem}_tail_from_cpacket.bin"
        cpacket_path.write_bytes(cpacket_blob)
        artifacts["cpacket_probe_path"] = str(cpacket_path)

    startcode_artifact = tail_startcode_artifact_candidate(
        decrypted_tail, marker=CONTAINER_PROBE_MARKER
    )
    if startcode_artifact is not None:
        artifact_type, offset, artifact_blob = startcode_artifact
        if artifact_type == TAIL_ARTIFACT_CONTAINER_PROBE:
            container_path = dump_dir / f"{stem}_tail_from_container_probe.bin"
            container_path.write_bytes(artifact_blob)
            artifacts["container_probe_path"] = str(container_path)
            artifacts["container_probe_offset"] = str(offset)
        elif artifact_type == TAIL_ARTIFACT_H264_FROM_STARTCODE:
            h264_path = dump_dir / f"{stem}_tail_from_startcode.h264"
            h264_path.write_bytes(artifact_blob)
            artifacts["h264_from_startcode_path"] = str(h264_path)
            artifacts["h264_from_startcode_offset"] = str(offset)
    return artifacts
