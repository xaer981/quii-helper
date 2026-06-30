import json
import sys
from collections.abc import Callable
from typing import Any, cast


def configure_console_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            cast(Callable[..., Any], reconfigure)(errors="backslashreplace")


def emit_json_line(obj: object) -> None:
    if isinstance(obj, (dict, list)):
        print(json.dumps(obj, ensure_ascii=True))
    else:
        print(obj)


__all__ = ["configure_console_output", "emit_json_line"]
