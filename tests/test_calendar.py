# ABOUTME: Tests for the calendar / wear log — logging items and outfits on
# ABOUTME: a day, removing them, the month grid, and derived wear counts.
from __future__ import annotations

import datetime

import db as db_module


def _outfit(flask_app, add_item, outfit_id="o0001", items=("001", "002")):
    for i in items:
        add_item(i)
    with flask_app.app_context():
        db_module.save_outfit({
            "id": outfit_id, "name": "look", "vibes": [], "created_at": "2026-09-01T00:00:00",
            "layout": [{"id": i, "x": 10, "y": 10, "w": 100, "rot": 0} for i in items],
        })


# ------------------------------------------------------------- db layer --

def test_log_and_unlog_loose_items(flask_app, add_item):
    add_item("001")
    add_item("002")
    with flask_app.app_context():
        db_module.log_items_worn("2026-09-05", ["001", "002"])
        worn = db_module.wears_on("2026-09-05")
        assert sorted(it["id"] for it in worn["items"]) == ["001", "002"]

        db_module.unlog_item("2026-09-05", "001")
        assert [it["id"] for it in db_module.wears_on("2026-09-05")["items"]] == ["002"]


def test_logging_an_outfit_counts_wears_for_each_piece(flask_app, add_item):
    _outfit(flask_app, add_item, items=("001", "002"))
    with flask_app.app_context():
        db_module.log_outfit_worn("2026-09-06", "o0001")
        assert db_module.get_item("001")["wear_count"] == 1
        assert db_module.get_item("002")["wear_count"] == 1
        worn = db_module.wears_on("2026-09-06")
        assert [o["id"] for o in worn["outfits"]] == ["o0001"]
        assert worn["items"] == []  # the pieces are under the outfit, not loose


def test_unlog_outfit_removes_all_its_pieces_for_that_day(flask_app, add_item):
    _outfit(flask_app, add_item, items=("001", "002"))
    with flask_app.app_context():
        db_module.log_outfit_worn("2026-09-06", "o0001")
        db_module.unlog_outfit("2026-09-06", "o0001")
        assert db_module.get_item("001")["wear_count"] == 0
        assert db_module.wears_on("2026-09-06") == {"items": [], "outfits": []}


def test_month_summary_only_lists_days_with_wears(flask_app, add_item):
    add_item("001")
    with flask_app.app_context():
        db_module.log_items_worn("2026-09-05", ["001"])
        db_module.log_items_worn("2026-10-01", ["001"])
        summary = db_module.wear_summary_for_month(2026, 9)
    assert list(summary) == ["2026-09-05"]
    assert summary["2026-09-05"]["item_ids"] == ["001"]


# ------------------------------------------------------------- routes --

def test_calendar_page_renders(client, add_item):
    assert client.get("/calendar").status_code == 200
    assert client.get("/calendar/2026/9").status_code == 200
    assert client.get("/calendar/2026/13").status_code == 404


def test_day_page_and_logging_flow(client, flask_app, add_item):
    add_item("001", name="the shirt")
    add_item("002", name="the pants")

    assert client.get("/calendar/day/2026-09-05").status_code == 200

    resp = client.post("/calendar/day/2026-09-05", data={"item_id": ["001", "002"]})
    assert resp.status_code == 302
    body = client.get("/calendar/day/2026-09-05").data.decode()
    assert "the shirt" in body and "the pants" in body

    client.post("/calendar/day/2026-09-05/remove", data={"kind": "item", "id": "001"})
    body = client.get("/calendar/day/2026-09-05").data.decode()
    assert "the pants" in body
    with flask_app.app_context():
        assert db_module.get_item("001")["wear_count"] == 0
        assert db_module.get_item("002")["wear_count"] == 1


def test_cannot_log_a_future_day(client, add_item):
    add_item("001")
    future = (datetime.date.today() + datetime.timedelta(days=3)).isoformat()
    assert client.get(f"/calendar/day/{future}").status_code == 404
    assert client.post(f"/calendar/day/{future}", data={"item_id": "001"}).status_code == 400


def test_bad_date_is_404(client):
    assert client.get("/calendar/day/not-a-date").status_code == 404


def test_worn_today_button_logs_into_the_calendar(client, flask_app, add_item):
    add_item("001")
    client.post("/item/001/worn")
    today = datetime.date.today().isoformat()
    with flask_app.app_context():
        assert [it["id"] for it in db_module.wears_on(today)["items"]] == ["001"]


# ------------------------------------------------------- day comfort/notes --

def test_day_log_round_trips(flask_app):
    with flask_app.app_context():
        assert db_module.get_day_log("2026-09-05") == {"comfort": None, "notes": ""}
        db_module.save_day_log("2026-09-05", 3, "cozy and warm")
        assert db_module.get_day_log("2026-09-05") == {"comfort": 3, "notes": "cozy and warm"}


def test_day_log_saving_both_empty_clears_the_row(flask_app):
    with flask_app.app_context():
        db_module.save_day_log("2026-09-05", 2, "note")
        db_module.save_day_log("2026-09-05", None, "")
        assert db_module.get_day_log("2026-09-05") == {"comfort": None, "notes": ""}


def test_day_log_note_only_is_fine(flask_app):
    with flask_app.app_context():
        db_module.save_day_log("2026-09-05", None, "just notes, no rating")
        assert db_module.get_day_log("2026-09-05") == {"comfort": None, "notes": "just notes, no rating"}


def test_note_route_saves_and_shows_on_the_day_page(client):
    resp = client.post("/calendar/day/2026-09-05/note", data={"comfort": "2", "notes": "great fit"})
    assert resp.status_code == 302
    body = client.get("/calendar/day/2026-09-05").data.decode()
    assert "great fit" in body
    assert 'value="2" checked' in body


def test_note_route_ignores_out_of_range_comfort(client, flask_app):
    client.post("/calendar/day/2026-09-05/note", data={"comfort": "99", "notes": "x"})
    with flask_app.app_context():
        assert db_module.get_day_log("2026-09-05")["comfort"] is None


def test_note_fields_are_optional_and_independent_of_logged_items(client, add_item):
    add_item("001", name="a shirt")
    client.post("/calendar/day/2026-09-05", data={"item_id": ["001"]})
    client.post("/calendar/day/2026-09-05/note", data={"notes": "wore it to the park"})
    body = client.get("/calendar/day/2026-09-05").data.decode()
    assert "a shirt" in body
    assert "wore it to the park" in body


# --------------------------------------------------- month grid: outfits --

def test_month_grid_shows_an_outfit_as_an_arranged_board(client, flask_app, add_item):
    _outfit(flask_app, add_item, items=("001", "002"))
    with flask_app.app_context():
        db_module.log_outfit_worn("2026-09-06", "o0001")
    body = client.get("/calendar/2026/9").data.decode()
    assert "calminiboard" in body
    assert "left: " in body and "top: " in body   # positioned pieces, not a flat row


def test_month_grid_caps_loose_item_thumbnails(client, flask_app, add_item):
    for i in range(1, 7):
        add_item(f"{i:03d}")
    with flask_app.app_context():
        db_module.log_items_worn("2026-09-05", [f"{i:03d}" for i in range(1, 7)])
    body = client.get("/calendar/2026/9").data.decode()
    assert "+2" in body   # 6 items, 4 shown, 2 more
