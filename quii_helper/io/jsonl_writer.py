import json
from pathlib import Path

from quii_helper.io.output_paths import data_file_path


def append_jsonl(path: str | Path, payload: dict) -> None:
    path = data_file_path(path)
    with path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(payload, ensure_ascii=True) + "\n")
