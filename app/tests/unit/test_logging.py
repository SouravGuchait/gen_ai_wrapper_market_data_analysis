import logging
from pathlib import Path

from app.core.logging import configure_logging


def test_configure_logging_writes_rotating_file(tmp_path: Path) -> None:
    log_file = tmp_path / "ai" / "app.log"
    configure_logging("INFO", str(log_file))

    logger = logging.getLogger("app.tests.unit.test_logging")
    logger.info("container logging ready")

    assert log_file.is_file()
    contents = log_file.read_text(encoding="utf-8")
    assert "container logging ready" in contents
