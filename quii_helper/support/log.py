import sys

from loguru import logger

from quii_helper.config.settings_loader import load_environment_settings

_SINK_ID: int | None = None
_DISABLED_LEVELS = {"OFF", "NONE", "DISABLED", "FALSE", "0"}
logger.disable("quii_helper")


def configure_logging(
    level: str | None = None, *, replace_existing: bool = False
) -> None:
    """Enable library console logs explicitly, preserving application sinks.

    Standalone examples use `replace_existing=True` because they own the
    process logging setup. Embedding applications can instead configure Loguru
    themselves and call `logger.enable("quii_helper")`.
    """
    global _SINK_ID

    default_level = (
        None if level is not None else load_environment_settings().log_level
    )
    resolved_level = (level or default_level or "INFO").strip().upper()
    if replace_existing:
        logger.remove()
    elif _SINK_ID is not None:
        try:
            logger.remove(_SINK_ID)
        except ValueError:
            pass  # The application may already have removed our sink.
    _SINK_ID = None
    if resolved_level not in _DISABLED_LEVELS:
        logger.enable("quii_helper")
        _SINK_ID = logger.add(
            sys.stderr,
            level=resolved_level,
            filter=lambda record: (record["name"] or "").startswith(
                "quii_helper."
            ),
            format="{time:HH:mm:ss.SSS} | {level:<8} | {message}",
            backtrace=False,
            diagnose=False,
        )
    else:
        logger.disable("quii_helper")


__all__ = ["configure_logging", "logger"]
