import logging
from pathlib import Path

import pytest

from app.core.logging import configure_logging


def test_configure_logging_writes_rotating_file(tmp_path: Path) -> None:
    log_file = tmp_path / "ai" / "app.log"
    configure_logging("INFO", str(log_file))

    logger = logging.getLogger("app.tests.unit.test_logging")
    logger.info("container logging ready")

    assert log_file.is_file()
    contents = log_file.read_text(encoding="utf-8")
    assert "container logging ready" in contents


def test_configure_logging_falls_back_when_permission_denied(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    blocked_root = tmp_path / "noperm"
    blocked_root.mkdir()
    blocked_root.chmod(0o500)
    blocked = blocked_root / "nested" / "app.log"
    try:
        configure_logging("INFO", str(blocked), allow_fallback=True)
    finally:
        blocked_root.chmod(0o700)

    fallback = tmp_path / "logs" / "app.log"
    assert fallback.is_file()


def test_configure_logging_raises_without_fallback(tmp_path: Path) -> None:
    blocked_root = tmp_path / "noperm"
    blocked_root.mkdir()
    blocked_root.chmod(0o500)
    blocked = blocked_root / "nested" / "app.log"
    try:
        with pytest.raises(PermissionError):
            configure_logging("INFO", str(blocked), allow_fallback=False)
    finally:
        blocked_root.chmod(0o700)
