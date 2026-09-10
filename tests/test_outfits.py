# ABOUTME: Tests for the outfits list — the arranged mini-board thumbnail
# ABOUTME: and the edit/delete controls behind the edit-mode toggle.
from __future__ import annotations

import db as db_module

OUTFIT = {
    "id": "o0001",
    "name": "monday look",
    "vibes": ["daytime"],
    "created_at": "2026-09-09T10:00:00",
    "layout": [
        {"id": "001", "x": 120, "y": 62, "w": 300, "rot": 5},
        {"id": "002", "x": 0, "y": 310, "w": 150, "rot": -3},
    ],
}


def _seed(flask_app, add_item):
    add_item("001")
    add_item("002")
    with flask_app.app_context():
        db_module.save_outfit(OUTFIT)


def test_miniboard_places_pieces_by_percentage(client, flask_app, add_item):
    _seed(flask_app, add_item)
    body = client.get("/outfits").data.decode()
    assert "miniboard" in body
    # 120/600 = 20%, 62/620 = 10%, 300/600 = 50%
    assert "left: 20.0%" in body
    assert "top: 10.0%" in body
    assert "width: 50.0%" in body
    assert "rotate(5" in body
    # second piece: 310/620 = 50%
    assert "top: 50.0%" in body


def test_miniboard_uses_thumbnails(client, flask_app, add_item):
    _seed(flask_app, add_item)
    body = client.get("/outfits").data.decode()
    assert "/thumbs/001.png" in body
    assert "/photos/001.png" not in body


def test_edit_toggle_and_per_card_controls_present(client, flask_app, add_item):
    _seed(flask_app, add_item)
    body = client.get("/outfits").data.decode()
    assert 'id="edit-toggle"' in body
    assert '/outfits/o0001/edit' in body
    assert 'action="/outfits/o0001/delete"' in body


def test_no_edit_toggle_when_there_are_no_outfits(client):
    body = client.get("/outfits").data.decode()
    assert 'id="edit-toggle"' not in body
    assert "no outfits saved yet" in body


def test_delete_from_list_removes_the_outfit(client, flask_app, add_item):
    _seed(flask_app, add_item)
    resp = client.post("/outfits/o0001/delete")
    assert resp.status_code == 302
    with flask_app.app_context():
        assert db_module.get_outfit("o0001") is None


def test_missing_piece_item_is_skipped_not_crashed(client, flask_app, add_item):
    add_item("001")
    with flask_app.app_context():
        db_module.save_outfit({
            "id": "o0001", "name": "x", "vibes": [], "created_at": "2026-09-09T00:00:00",
            "layout": [
                {"id": "001", "x": 10, "y": 10, "w": 100, "rot": 0},
                {"id": "404", "x": 20, "y": 20, "w": 100, "rot": 0},  # deleted item
            ],
        })
    resp = client.get("/outfits")
    assert resp.status_code == 200
    assert resp.data.decode().count("minipiece") == 1
