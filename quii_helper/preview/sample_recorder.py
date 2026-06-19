import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from quii_helper.io.jsonl_writer import append_jsonl


@dataclass
class PreviewJsonlSampleRecorder:
    sample_path: Path
    limit: int
    enabled: bool
    seen_hashes: set[str] = field(default_factory=set)

    def record(self, blob: bytes, payload: dict[str, Any]) -> bool:
        blob_hash = hashlib.sha1(blob).hexdigest()
        if blob_hash in self.seen_hashes:
            return False
        if len(self.seen_hashes) >= self.limit:
            return False
        self.seen_hashes.add(blob_hash)
        if not self.enabled:
            return False
        append_jsonl(self.sample_path, {"sha1": blob_hash, **payload})
        return True
