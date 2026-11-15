"""Shared fixtures. Point file logs at a writable temp path for unit tests."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from app.core.config import get_settings


@pytest.fixture(autouse=True)
def _writable_log_file_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[None]:
    monkeypatch.setenv("LOG_FILE_PATH", str(tmp_path / "app.log"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
