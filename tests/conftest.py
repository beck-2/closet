# ABOUTME: Shared pytest fixtures — a Flask test client wired to a throwaway
# ABOUTME: SQLite database and data directory, plus helpers to seed items.
from __future__ import annotations

import json
from pathlib import Path

import pytest

import app as app_module
import db as db_module


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    d = tmp_path / "data"
    (d / "processed").mkdir(parents=True)
    (d / "raw").mkdir(parents=True)
    (d / "originals").mkdir(parents=True)
    return d


@pytest.fixture
def flask_app(data_dir: Path):
    """The real app object, pointed at a fresh per-test database."""
    db_path = data_dir / "closet.db"
    app_module.app.config.update(TESTING=True, DB_PATH=str(db_path))
    with app_module.app.app_context():
        db_module.init_db(db_path)
    yield app_module.app


@pytest.fixture
def client(flask_app):
    return flask_app.test_client()


@pytest.fixture
def add_item(flask_app):
    """Insert an item row directly (no photo pipeline). Returns its id."""
    def _add(item_id: str = "001", **fields) -> str:
        record = {
            "name": "test piece",
            "item_type": "top",
            "color": ["black"],
            "comfort": 3,
            "fit": 2,
            "condition": 3,
            "vibes": [],
            "source": "thrifted",
            "price": 10.0,
            "date_acquired": None,
            "season": [],
            "notes": "",
            "images": ["data/processed/%s.png" % item_id],
            "raw_images": ["data/raw/%s.jpeg" % item_id],
        }
        record.update(fields)
        with flask_app.app_context():
            db_module.save_item(item_id, record)
        return item_id

    return _add
