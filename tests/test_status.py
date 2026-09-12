# ABOUTME: Tests for item status tags (clean/dirty/loaned/lost/broken),
# ABOUTME: the quick-set route, and auto-dirtying clothing when it's worn.
from __future__ import annotations

import db as db_module


def test_new_item_defaults_to_clean(client, flask_app, add_item):
    add_item("001")
    with flask_app.app_context():
        item = db_module.get_item("001")
    assert item["status"] == "clean"
    assert item["status_note"] is None


def test_set_item_status_round_trips(client, flask_app, add_item):
    add_item("001")
    with flask_app.app_context():
        db_module.set_item_status("001", "loaned", "sam")
        item = db_module.get_item("001")
    assert item["status"] == "loaned"
    assert item["status_note"] == "sam"


def test_status_route_sets_status_and_redirects(client, flask_app, add_item):
    add_item("001")
    resp = client.post("/item/001/status", data={"status": "broken"})
    assert resp.status_code == 302
    with flask_app.app_context():
        assert db_module.get_item("001")["status"] == "broken"


def test_status_route_saves_a_loaned_note(client, flask_app, add_item):
    add_item("001")
    client.post("/item/001/status", data={"status": "loaned", "note": "  jamie  "})
    with flask_app.app_context():
        item = db_module.get_item("001")
    assert item["status"] == "loaned"
    assert item["status_note"] == "jamie"


def test_status_route_drops_the_note_for_non_loaned_statuses(client, flask_app, add_item):
    add_item("001")
    client.post("/item/001/status", data={"status": "loaned", "note": "jamie"})
    client.post("/item/001/status", data={"status": "clean", "note": "jamie"})
    with flask_app.app_context():
        item = db_module.get_item("001")
    assert item["status"] == "clean"
    assert item["status_note"] is None


def test_status_route_rejects_an_unknown_status(client, add_item):
    add_item("001")
    resp = client.post("/item/001/status", data={"status": "sparkly"})
    assert resp.status_code == 400


def test_status_route_404s_for_a_missing_item(client):
    assert client.post("/item/999/status", data={"status": "dirty"}).status_code == 404


def test_item_view_renders_status_pills_and_loaned_note(client, flask_app, add_item):
    add_item("001")
    with flask_app.app_context():
        db_module.set_item_status("001", "loaned", "jamie")
    body = client.get("/item/001").data.decode()
    assert 'class="statuspill status-loaned active"' in body
    assert 'value="jamie"' in body


def test_closet_card_shows_a_badge_for_non_clean_status(client, flask_app, add_item):
    add_item("001")
    with flask_app.app_context():
        db_module.set_item_status("001", "dirty", None)
    body = client.get("/").data.decode()
    assert 'class="cardstatus status-dirty"' in body


def test_closet_card_shows_no_badge_for_clean_status(client, add_item):
    add_item("001")
    body = client.get("/").data.decode()
    assert "cardstatus" not in body


# --------------------------------------------- auto-dirty clothing on wear --

def test_logging_a_loose_clothing_item_marks_it_dirty(client, flask_app, add_item):
    add_item("001", item_type="top")
    with flask_app.app_context():
        db_module.log_items_worn("2026-09-05", ["001"])
        assert db_module.get_item("001")["status"] == "dirty"


def test_logging_a_loose_jewelry_item_does_not_mark_it_dirty(client, flask_app, add_item):
    add_item("001", item_type="jewelry", jewelry_subtype="earrings")
    with flask_app.app_context():
        db_module.log_items_worn("2026-09-05", ["001"])
        assert db_module.get_item("001")["status"] == "clean"


def test_logging_a_loose_scarf_does_not_mark_it_dirty(client, flask_app, add_item):
    add_item("001", item_type="scarf")
    with flask_app.app_context():
        db_module.log_items_worn("2026-09-05", ["001"])
        assert db_module.get_item("001")["status"] == "clean"


def test_logging_an_outfit_dirties_its_clothing_pieces_only(client, flask_app, add_item):
    add_item("001", item_type="top")
    add_item("002", item_type="shoes")
    outfit = {
        "id": "o0001", "name": "look", "vibes": [], "created_at": "2026-09-01T00:00:00",
        "layout": [
            {"id": "001", "x": 0, "y": 0, "w": 100, "rot": 0},
            {"id": "002", "x": 0, "y": 0, "w": 100, "rot": 0},
        ],
    }
    with flask_app.app_context():
        db_module.save_outfit(outfit)
        db_module.log_outfit_worn("2026-09-05", "o0001")
        assert db_module.get_item("001")["status"] == "dirty"
        assert db_module.get_item("002")["status"] == "clean"


def test_saving_the_day_board_dirties_newly_placed_clothing(client, flask_app, add_item):
    add_item("001", item_type="hoodie")
    placement = {"id": "001", "x": 0, "y": 0, "w": 100, "rot": 0}
    with flask_app.app_context():
        db_module.save_day_layout("2026-09-05", [placement])
        assert db_module.get_item("001")["status"] == "dirty"


def test_manually_cleaning_an_already_placed_item_is_not_re_dirtied_on_resave(client, flask_app, add_item):
    add_item("001", item_type="hoodie")
    placement = {"id": "001", "x": 0, "y": 0, "w": 100, "rot": 0}
    with flask_app.app_context():
        db_module.save_day_layout("2026-09-05", [placement])
        db_module.set_item_status("001", "clean", None)
        # Resaving the exact same board shouldn't touch an item that was
        # already logged for that day — it's not "newly placed" anymore.
        db_module.save_day_layout("2026-09-05", [placement])
        assert db_module.get_item("001")["status"] == "clean"


def test_mark_worn_route_dirties_a_clothing_item(client, flask_app, add_item):
    add_item("001", item_type="dress")
    client.post("/item/001/worn")
    with flask_app.app_context():
        assert db_module.get_item("001")["status"] == "dirty"


# ------------------------------------------------------------------ sources --

def test_add_form_offers_new_sources(client):
    body = client.get("/add").data.decode()
    assert ">idk<" in body and ">secondhand<" in body
