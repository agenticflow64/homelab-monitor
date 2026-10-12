import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "agent"))

from fastapi.testclient import TestClient  # noqa: E402

import app.main as main  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """Клиент с подменённым хранилищем (во временную папку) и без cooldown-памяти."""
    monkeypatch.setattr(main, "store", main.AlertStore(str(tmp_path)))
    with TestClient(main.app) as test_client:
        yield test_client
