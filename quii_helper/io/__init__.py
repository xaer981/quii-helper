"""Runtime artifact storage helpers."""

from quii_helper.support.lazy import lazy_exports

_EXPORTS = {
    "DATA_DIR": ("quii_helper.io.paths", "DATA_DIR"),
    "PROJECT_ROOT": ("quii_helper.io.paths", "PROJECT_ROOT"),
    "append_jsonl": ("quii_helper.io.jsonl_writer", "append_jsonl"),
    "data_base_path": ("quii_helper.io.output_paths", "data_base_path"),
    "data_file_path": ("quii_helper.io.output_paths", "data_file_path"),
    "data_path": ("quii_helper.io.paths", "data_path"),
    "ensure_data_dir": ("quii_helper.io.paths", "ensure_data_dir"),
    "resolve_data_dir": ("quii_helper.io.paths", "resolve_data_dir"),
    "resolve_data_path": ("quii_helper.io.paths", "resolve_data_path"),
    "timestamped_output_base": (
        "quii_helper.io.paths",
        "timestamped_output_base",
    ),
}

__all__, __getattr__ = lazy_exports(__name__, _EXPORTS, globals())
