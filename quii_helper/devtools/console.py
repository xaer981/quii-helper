import json
import sys


def configure_console_output() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="backslashreplace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(errors="backslashreplace")


def emit_json_line(obj: object) -> None:
    if isinstance(obj, (dict, list)):
        print(json.dumps(obj, ensure_ascii=True))
    else:
        print(obj)


__all__ = ["configure_console_output", "emit_json_line"]
