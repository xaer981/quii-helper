from pathlib import Path

from quii_helper.diagnostics.wrapped.tail_candidate_extractors import (
    candidate_cpacket_from_decrypted_tail,
)
from quii_helper.diagnostics.wrapped.tail_crypto import (
    decrypt_wrapped_quii_tail_bytes,
)
from quii_helper.diagnostics.wrapped.tail_probe import (
    is_container_probe_before_start_code,
)
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

    start4 = decrypted_tail.find(b"\x00\x00\x00\x01")
    if start4 >= 0:
        if is_container_probe_before_start_code(decrypted_tail, start4):
            container_start = start4 - 4
            container_path = dump_dir / f"{stem}_tail_from_container_probe.bin"
            container_path.write_bytes(decrypted_tail[container_start:])
            artifacts["container_probe_path"] = str(container_path)
            artifacts["container_probe_offset"] = str(container_start)
        else:
            h264_path = dump_dir / f"{stem}_tail_from_startcode.h264"
            h264_path.write_bytes(decrypted_tail[start4:])
            artifacts["h264_from_startcode_path"] = str(h264_path)
            artifacts["h264_from_startcode_offset"] = str(start4)
    return artifacts
