import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def configure_logging(level: str, file_path: str):
    log_path = Path(file_path).expanduser().resolve()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    file_handler = RotatingFileHandler(log_path, maxBytes=5_000_000, backupCount=3, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logging.basicConfig(
        level=level.upper(),
        handlers=[console, file_handler],
        force=True,
    )
