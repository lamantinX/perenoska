from __future__ import annotations

import os
import shutil
import tempfile
import uuid
from pathlib import Path

import _pytest.tmpdir
import pytest

def pytest_load_initial_conftests(early_config, parser, args) -> None:
    root = Path(__file__).resolve().parent.parent
    temp_root = root / ".tmp" / "pytest-runtime"
    temp_root.mkdir(parents=True, exist_ok=True)

    temp_value = str(temp_root)
    for key in ("TMP", "TEMP", "TMPDIR"):
        os.environ[key] = temp_value

    tempfile.tempdir = temp_value


def pytest_configure(config) -> None:
    # Windows sandbox cleanup of pytest temp dirs is unreliable here; skipping
    # symlink cleanup avoids teardown crashes without affecting test behavior.
    _pytest.tmpdir.cleanup_dead_symlinks = lambda root: None


@pytest.fixture
def tmp_path() -> Path:
    root = Path(__file__).resolve().parent.parent / ".tmp" / "test-fixtures"
    root.mkdir(parents=True, exist_ok=True)

    path = root / uuid.uuid4().hex
    path.mkdir()

    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)
