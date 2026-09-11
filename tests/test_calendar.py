# ABOUTME: Tests for the calendar / wear log — logging items and outfits on
# ABOUTME: a day, the ad-hoc day board, the month grid, and derived wear counts.
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


def _board_post(client, date, placements):
    return client.post(f"/calendar/day/{date}/board", json={"items": placements})


def _placement(item_id, x=10, y=10, w=200, rot=0):
    return {"id": item_id, "x": x, "y": y, "w": w, "rot": rot}


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


# --------------------------------------------------------- day board (db) --

def test_day_layout_round_trips(flask_app, add_item):
    add_item("001")
    add_item("002")
    with flask_app.app_context():
        assert db_module.get_day_layout("2026-09-05") == []
        db_module.save_day_layout("2026-09-05", [_placement("001", x=5, y=6, w=150, rot=2)])
        layout = db_module.get_day_layout("2026-09-05")
    assert layout == [{"id": "001", "x": 5, "y": 6, "w": 150, "rot": 2}]


def test_saving_the_day_layout_logs_placed_pieces_as_worn(flask_app, add_item):
    add_item("001")
    with flask_app.app_context():
        db_module.save_day_layout("2026-09-05", [_placement("001")])
        assert db_module.get_item("001")["wear_count"] == 1
        assert [it["id"] for it in db_module.wears_on("2026-09-05")["items"]] == ["001"]


def test_resaving_the_day_layout_without_a_piece_unlogs_it(flask_app, add_item):
    add_item("001")
    add_item("002")
    with flask_app.app_context():
        db_module.save_day_layout("2026-09-05", [_placement("001"), _placement("002")])
        db_module.save_day_layout("2026-09-05", [_placement("002")])  # dropped 001
        assert db_module.get_item("001")["wear_count"] == 0
        assert db_module.get_item("002")["wear_count"] == 1
        assert [p["id"] for p in db_module.get_day_layout("2026-09-05")] == ["002"]


def test_day_layout_ignores_unknown_item_ids(flask_app, add_item):
    add_item("001")
    with flask_app.app_context():
        db_module.save_day_layout("2026-09-05", [_placement("001"), _placement("999")])
        assert [p["id"] for p in db_module.get_day_layout("2026-09-05")] == ["001"]


# ------------------------------------------------------------- routes --

def test_calendar_page_renders(client, add_item):
    assert client.get("/calendar").status_code == 200
    assert client.get("/calendar/2026/9").status_code == 200
    assert client.get("/calendar/2026/13").status_code == 404


def test_day_page_board_save_and_resave_flow(client, flask_app, add_item):
    add_item("001", name="the shirt")
    add_item("002", name="the pants")

    assert client.get("/calendar/day/2026-09-05").status_code == 200

    resp = _board_post(client, "2026-09-05", [_placement("001"), _placement("002")])
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True
    body = client.get("/calendar/day/2026-09-05").data.decode()
    assert "the shirt" in body and "the pants" in body

    _board_post(client, "2026-09-05", [_placement("002")])  # remove the shirt by resaving
    with flask_app.app_context():
        assert db_module.get_item("001")["wear_count"] == 0
        assert db_module.get_item("002")["wear_count"] == 1


def test_board_route_rejects_malformed_placement(client, add_item):
    add_item("001")
    resp = _board_post(client, "2026-09-05", [{"id": "001", "x": "nope"}])
    assert resp.status_code == 400
    assert resp.get_json()["ok"] is False


def test_day_page_auto_places_already_logged_loose_items(client, flask_app, add_item):
    # Logged via the quick "Worn today" path, i.e. with no saved position yet.
    add_item("001", name="quick logged")
    with flask_app.app_context():
        db_module.log_items_worn("2026-09-05", ["001"])
    body = client.get("/calendar/day/2026-09-05").data.decode()
    assert "quick logged" in body
    # board_pieces is handed to the JS as JSON; the first auto-placed piece
    # lands at the default staggering origin (60, 40).
    assert '"item_id": "001"' in body
    assert '"x": 60' in body and '"y": 40' in body


def test_cannot_log_a_future_day(client, add_item):
    add_item("001")
    future = (datetime.date.today() + datetime.timedelta(days=3)).isoformat()
    assert client.get(f"/calendar/day/{future}").status_code == 404
    assert _board_post(client, future, [_placement("001")]).status_code == 400
    assert client.post(f"/calendar/day/{future}", data={"outfit_id": "o0001"}).status_code == 400


def test_bad_date_is_404(client):
    assert client.get("/calendar/day/not-a-date").status_code == 404


def test_worn_today_button_logs_into_the_calendar(client, flask_app, add_item):
    add_item("001")
    client.post("/item/001/worn")
    today = datetime.date.today().isoformat()
    with flask_app.app_context():
        assert [it["id"] for it in db_module.wears_on(today)["items"]] == ["001"]


def test_removing_a_logged_outfit(client, flask_app, add_item):
    _outfit(flask_app, add_item, items=("001", "002"))
    client.post("/calendar/day/2026-09-06", data={"outfit_id": "o0001"})
    body = client.get("/calendar/day/2026-09-06").data.decode()
    assert "look" in body

    client.post("/calendar/day/2026-09-06/remove", data={"id": "o0001"})
    with flask_app.app_context():
        assert db_module.wears_on("2026-09-06")["outfits"] == []


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
    _board_post(client, "2026-09-05", [_placement("001")])
    client.post("/calendar/day/2026-09-05/note", data={"notes": "wore it to the park"})
    body = client.get("/calendar/day/2026-09-05").data.decode()
    assert "a shirt" in body
    assert "wore it to the park" in body


# --------------------------------------------------------- month grid --

def test_month_grid_shows_an_outfit_as_an_arranged_board(client, flask_app, add_item):
    _outfit(flask_app, add_item, items=("001", "002"))
    with flask_app.app_context():
        db_module.log_outfit_worn("2026-09-06", "o0001")
    body = client.get("/calendar/2026/9").data.decode()
    assert "calminiboard" in body
    assert "left: " in body and "top: " in body   # positioned pieces, not a flat row


def test_month_grid_shows_loose_items_as_a_board_too(client, flask_app, add_item):
    add_item("001", name="a")
    add_item("002", name="b")
    with flask_app.app_context():
        db_module.log_items_worn("2026-09-05", ["001", "002"])
    body = client.get("/calendar/2026/9").data.decode()
    assert "calminiboard" in body


def test_month_grid_caps_tiles_per_day_with_an_overflow_badge(client, flask_app, add_item):
    _outfit(flask_app, add_item, outfit_id="o0001", items=("001", "002"))
    add_item("003", name="loose one")
    with flask_app.app_context():
        db_module.log_outfit_worn("2026-09-06", "o0001")
        db_module.log_items_worn("2026-09-06", ["003"])  # a second tile: outfit + loose board
    body = client.get("/calendar/2026/9").data.decode()
    assert body.count("calminiboard") == 1   # only one tile shown
    assert "+1" in body
