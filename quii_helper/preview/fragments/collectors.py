from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from quii_helper.diagnostics.wrapped.payload.inner_analysis import (
    analyze_partial_wrapped_inner,
)
from quii_helper.diagnostics.wrapped.tail.artifacts import (
    dump_partial_tail_artifacts,
)
from quii_helper.diagnostics.wrapped.tail.candidate_extractors import (
    candidate_container_probe,
    candidate_container_probe_from_partial_payload,
    candidate_cpacket_stream,
    candidate_embedded_h264,
)
from quii_helper.models.packets import PacketMeta
from quii_helper.preview.outputs.manager.sample_recorder import (
    PreviewJsonlSampleRecorder,
)
from quii_helper.preview.outputs.manager.state import (
    fragment_partial_sample_payload,
)
from quii_helper.protocols.quii.blob import decode_quii_blob


@dataclass
class FragmentPartialCollector:
    key: str
    sample_path: Path
    dump_dir: Path
    save_diagnostic_artifacts: bool
    sample_limit: int
    seen_hashes: set[str] = field(default_factory=set)
    embedded_h264_candidates: list[bytes] = field(default_factory=list)
    container_probe_candidates: list[bytes] = field(default_factory=list)
    cpacket_candidates: list[bytes] = field(default_factory=list)
    _samples: PreviewJsonlSampleRecorder = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._samples = PreviewJsonlSampleRecorder(
            sample_path=self.sample_path,
            limit=self.sample_limit,
            enabled=self.save_diagnostic_artifacts,
            seen_hashes=self.seen_hashes,
        )

    def analyze(
        self, blob: bytes, *, source: str, meta: PacketMeta, message_index: int
    ) -> dict[str, Any] | None:
        if source != "wrapped_fragment_partial":
            return None

        analysis = analyze_partial_wrapped_inner(blob, self.key)
        payload_dec = analysis.get("payload_decode")
        partial_payload = blob[0x38:]
        if isinstance(payload_dec, dict) and payload_dec.get("plausible"):
            decoded_for_dump = decode_quii_blob(
                partial_payload, self.key, crypto_mode=2
            )
            embedded_h264 = candidate_embedded_h264(
                partial_payload, self.key, decoded_for_dump
            )
            if embedded_h264:
                self.embedded_h264_candidates.append(embedded_h264)

            container_probe_blob = candidate_container_probe(
                partial_payload, self.key, decoded_for_dump
            )
            if container_probe_blob:
                self.container_probe_candidates.append(container_probe_blob)

            cpacket_blob = candidate_cpacket_stream(
                partial_payload, self.key, decoded_for_dump
            )
            if cpacket_blob:
                self.cpacket_candidates.append(cpacket_blob)

            if self.save_diagnostic_artifacts:
                analysis.update(
                    dump_partial_tail_artifacts(
                        blob=partial_payload,
                        key=self.key,
                        decoded=decoded_for_dump,
                        dump_dir=self.dump_dir,
                        stem=f"msg_{message_index:03d}_{source}",
                    )
                )
        else:
            payload_probe = candidate_container_probe_from_partial_payload(
                partial_payload, self.key
            )
            if payload_probe:
                self.container_probe_candidates.append(payload_probe)

        self._samples.record(
            blob,
            fragment_partial_sample_payload(
                msg_index=message_index,
                source=source,
                meta=cast(dict[str, Any], meta),
                analysis=analysis,
            ),
        )

        return analysis
