from pathlib import Path

from quii_helper.io.paths import resolve_data_path


def data_file_path(path: str | Path) -> Path:
    return resolve_data_path(path)


def data_base_path(base_name: str | Path) -> Path:
    return resolve_data_path(base_name)
