from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.db import connect
from app.main import app, get_now
from app.seed import seed

NOW = datetime(2030, 3, 1, 10, 0, 0)


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("ORDERLOOP_DB", str(db_file))
    conn = connect(str(db_file))
    seed(conn, NOW)
    conn.close()
    app.dependency_overrides[get_now] = lambda: NOW
    yield TestClient(app)
    app.dependency_overrides.clear()
