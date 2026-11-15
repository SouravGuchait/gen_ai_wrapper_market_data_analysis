import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
_MAX_BYTES = 5_000_000
_BACKUP_COUNT = 3
_FALLBACK_LOG_PATH = Path("logs") / "app.log"


def _prepare_log_path(file_path: str, *, allow_fallback: bool) -> Path:
    log_path = Path(file_path).expanduser().resolve()
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        if not allow_fallback:
            raise
        log_path = _FALLBACK_LOG_PATH.resolve()
        log_path.parent.mkdir(parents=True, exist_ok=True)
    return log_path


def configure_logging(
    level: str,
    file_path: str,
    *,
    allow_fallback: bool = False,
) -> None:
    """Configure root logging to stdout and a rotating file."""
    log_path = _prepare_log_path(file_path, allow_fallback=allow_fallback)
    formatter = logging.Formatter(_LOG_FORMAT)
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    logging.basicConfig(
        level=level.upper(),
        handlers=[console, file_handler],
        force=True,
    )
    logging.getLogger(__name__).info("Logging configured path=%s", log_path)
