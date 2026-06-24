START_CODE4 = b"\x00\x00\x00\x01"
TAIL_ARTIFACT_CONTAINER_PROBE = "container_probe"
TAIL_ARTIFACT_H264_FROM_STARTCODE = "h264_from_startcode"
TailArtifactCandidate = tuple[str, int, bytes]


def tail_startcode_h264_candidate(
    decrypted_tail: bytes, *, marker: bytes
) -> bytes:
    start4 = decrypted_tail.find(START_CODE4)
    if start4 < 0:
        return b""
    if is_marker_before_offset(decrypted_tail, start4, marker=marker):
        return b""
    return decrypted_tail[start4:]


def tail_container_probe_candidate(
    decrypted_tail: bytes, *, marker: bytes
) -> bytes:
    start4 = decrypted_tail.find(START_CODE4)
    if start4 < len(marker):
        return b""
    if not is_marker_before_offset(decrypted_tail, start4, marker=marker):
        return b""
    return decrypted_tail[start4 - len(marker) :]


def partial_payload_container_candidate(
    payload: bytes, *, marker: bytes
) -> bytes:
    if not payload:
        return b""
    marker_offset = payload.find(marker)
    if marker_offset < 0:
        return b""
    return payload[marker_offset:]


def is_marker_before_offset(
    blob: bytes, offset: int, *, marker: bytes
) -> bool:
    return offset >= len(marker) and (
        blob[offset - len(marker) : offset] == marker
    )


def tail_startcode_artifact_candidate(
    decrypted_tail: bytes, *, marker: bytes
) -> TailArtifactCandidate | None:
    start4 = decrypted_tail.find(START_CODE4)
    if start4 < 0:
        return None
    if is_marker_before_offset(decrypted_tail, start4, marker=marker):
        container_start = start4 - len(marker)
        return (
            TAIL_ARTIFACT_CONTAINER_PROBE,
            container_start,
            decrypted_tail[container_start:],
        )
    return (
        TAIL_ARTIFACT_H264_FROM_STARTCODE,
        start4,
        decrypted_tail[start4:],
    )
