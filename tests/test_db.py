# ABOUTME: Tests for the SQLite storage layer — item/outfit round-trips,
# ABOUTME: atomic wear-count updates, and cascade deletes.
from __future__ import annotations

import db as db_module


def test_save_and_get_item_roundtrip(flask_app):
    record = {
        "name": "striped tee", "item_type": "tshirt", "color": ["red", "white"],
        "comfort": 3, "fit": 2, "condition": 3, "vibes": ["daytime"],
        "source": "thrifted", "price": 12.5, "date_acquired": "2025-03",
        "season": ["summer"], "notes": "soft",
        "images": ["data/processed/001.png", "data/processed/001_2.png"],
        "raw_images": ["data/raw/001.jpeg", "data/raw/001_2.jpeg"],
    }
    with flask_app.app_context():
        db_module.save_item("001", record)
        got = db_module.get_item("001")

    assert got["name"] == "striped tee"
    assert got["color"] == ["red", "white"]
    assert got["vibes"] == ["daytime"]
    assert got["images"] == ["data/processed/001.png", "data/processed/001_2.png"]
    assert got["raw_images"] == ["data/raw/001.jpeg", "data/raw/001_2.jpeg"]


def test_get_missing_item_returns_none(flask_app):
    with flask_app.app_context():
        assert db_module.get_item("999") is None


def test_save_item_replaces_images_not_appends(flask_app, add_item):
    add_item("002", images=["data/processed/002.png", "data/processed/002_2.png"],
             raw_images=["data/raw/002.jpeg", "data/raw/002_2.jpeg"])
    with flask_app.app_context():
        record = db_module.get_item("002")
        record["images"] = ["data/processed/002.png"]
        record["raw_images"] = ["data/raw/002.jpeg"]
        db_module.save_item("002", record)
        got = db_module.get_item("002")
    assert got["images"] == ["data/processed/002.png"]


def test_wear_count_is_derived_from_the_wear_log(flask_app, add_item):
    add_item("003")
    with flask_app.app_context():
        assert db_module.get_item("003")["wear_count"] == 0
        db_module.log_items_worn("2026-09-01", ["003"])
        db_module.log_items_worn("2026-09-05", ["003"])
        db_module.log_items_worn("2026-09-05", ["003"])  # same day again: no-op
        assert db_module.get_item("003")["wear_count"] == 2


def test_count_and_existing_ids(flask_app, add_item):
    add_item("001")
    add_item("007")
    with flask_app.app_context():
        assert db_module.count_items() == 2
        assert sorted(db_module.existing_item_ids()) == ["001", "007"]


def test_outfit_roundtrip_and_delete_cascade(flask_app, add_item):
    add_item("001")
    add_item("002")
    outfit = {
        "id": "o0001", "name": "look one", "vibes": ["going out"],
        "created_at": "2026-09-09T10:00:00",
        "layout": [
            {"id": "001", "x": 10, "y": 20, "w": 200, "rot": 1.5},
            {"id": "002", "x": 40, "y": 60, "w": 180, "rot": -2.0},
        ],
    }
    with flask_app.app_context():
        db_module.save_outfit(outfit)
        got = db_module.get_outfit("o0001")
        assert got["name"] == "look one"
        assert [p["id"] for p in got["layout"]] == ["001", "002"]
        assert got["layout"][0]["w"] == 200

        db_module.delete_outfit("o0001")
        assert db_module.get_outfit("o0001") is None
        remaining = db_module.get_db().execute(
            "SELECT COUNT(*) FROM outfit_items WHERE outfit_id = 'o0001'"
        ).fetchone()[0]
        assert remaining == 0


def test_save_outfit_update_keeps_created_at(flask_app, add_item):
    add_item("001")
    base = {
        "id": "o0001", "name": "v1", "vibes": [], "created_at": "2026-01-01T00:00:00",
        "layout": [{"id": "001", "x": 1, "y": 2, "w": 100, "rot": 0}],
    }
    with flask_app.app_context():
        db_module.save_outfit(base)
        updated = dict(base, name="v2", created_at="2026-12-31T23:59:59")
        db_module.save_outfit(updated)
        got = db_module.get_outfit("o0001")
    assert got["name"] == "v2"
    assert got["created_at"] == "2026-01-01T00:00:00"


def test_next_outfit_id_counts_up(flask_app, add_item):
    add_item("001")
    with flask_app.app_context():
        assert db_module.next_outfit_id() == "o0001"
        db_module.save_outfit({
            "id": "o0001", "name": "x", "vibes": [], "created_at": "2026-09-09T00:00:00",
            "layout": [{"id": "001", "x": 0, "y": 0, "w": 100, "rot": 0}],
        })
        assert db_module.next_outfit_id() == "o0002"
