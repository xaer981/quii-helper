"""Runtime artifact storage helpers."""

from importlib import import_module
from typing import Any

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

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    try:
        module_name, attr_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(
            f"module {__name__!r} has no attribute {name!r}"
        ) from exc
    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value
