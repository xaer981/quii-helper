import sys

from loguru import logger

from quii_helper.constants import LOG_LEVEL

_CONFIGURED = False
_DISABLED_LEVELS = {"OFF", "NONE", "DISABLED", "FALSE", "0"}


def configure_logging(level: str | None = None) -> None:
    global _CONFIGURED

    resolved_level = (level or LOG_LEVEL or "INFO").strip().upper()
    logger.remove()
    if resolved_level not in _DISABLED_LEVELS:
        logger.add(
            sys.stderr,
            level=resolved_level,
            format="{time:HH:mm:ss.SSS} | {level:<8} | {message}",
            backtrace=False,
            diagnose=False,
        )
    _CONFIGURED = True


if not _CONFIGURED:
    configure_logging()


__all__ = ["configure_logging", "logger"]
