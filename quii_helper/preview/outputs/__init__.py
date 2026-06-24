"""Backward-compatible preview output facade."""

from quii_helper.io.jsonl_writer import append_jsonl
from quii_helper.io.output_paths import data_base_path, data_file_path
from quii_helper.preview.fragments.embedded_h264 import (
    merge_annexb_candidates,
    merge_two_streams,
    write_embedded_h264_fallback,
)
from quii_helper.preview.outputs.probes.outputs import (
    write_container_probe_summary,
    write_cpacket_probe_summary,
)

_data_file_path = data_file_path
_data_base_path = data_base_path

__all__ = [
    "append_jsonl",
    "data_file_path",
    "data_base_path",
    "_data_file_path",
    "_data_base_path",
    "merge_annexb_candidates",
    "merge_two_streams",
    "write_container_probe_summary",
    "write_cpacket_probe_summary",
    "write_embedded_h264_fallback",
]
