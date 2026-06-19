import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from quii_helper.diagnostics.wrapped.inner_analysis import (
    analyze_partial_wrapped_inner,
)
from quii_helper.diagnostics.wrapped.tail_artifacts import (
    dump_partial_tail_artifacts,
)
from quii_helper.diagnostics.wrapped.tail_candidate_extractors import (
    candidate_container_probe,
    candidate_container_probe_from_partial_payload,
    candidate_cpacket_stream,
    candidate_embedded_h264,
)
from quii_helper.io.jsonl_writer import append_jsonl
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

    def analyze(
        self, blob: bytes, *, source: str, meta: dict, message_index: int
    ) -> dict | None:
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

        blob_hash = hashlib.sha1(blob).hexdigest()
        if (
            blob_hash not in self.seen_hashes
            and len(self.seen_hashes) < self.sample_limit
        ):
            self.seen_hashes.add(blob_hash)
            if self.save_diagnostic_artifacts:
                append_jsonl(
                    self.sample_path,
                    {
                        "sha1": blob_hash,
                        "msg_index": message_index,
                        "source": source,
                        "meta": meta,
                        "analysis": analysis,
                    },
                )

        return analysis
