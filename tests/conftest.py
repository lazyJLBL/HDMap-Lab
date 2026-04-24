from __future__ import annotations

from pathlib import Path

import pytest

from app.storage.runtime import DATA_DIR, RuntimeState


@pytest.fixture()
def runtime(tmp_path: Path) -> RuntimeState:
    state = RuntimeState(tmp_path / "test.sqlite")
    state.load_sample()
    return state


@pytest.fixture()
def sample_data_dir() -> Path:
    return DATA_DIR

