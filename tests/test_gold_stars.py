# ABOUTME: Tests for gold stars — a capped set of favourited pieces that
# ABOUTME: pin to the top of the closet; a 6th award bumps the oldest.
from __future__ import annotations

import db as db_module


def test_toggle_star_sets_then_clears(client, flask_app, add_item):
    add_item("001")
    client.post("/item/001/star")
    with flask_app.app_context():
        assert db_module.get_item("001")["starred"] is True
    client.post("/item/001/star")
    with flask_app.app_context():
        assert db_module.get_item("001")["starred"] is False


def test_star_toggle_redirects_to_item(client, add_item):
    add_item("001")
    resp = client.post("/item/001/star")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/item/001")


def test_star_missing_item_is_404(client):
    assert client.post("/item/999/star").status_code == 404


def test_sixth_star_bumps_the_oldest(client, flask_app, add_item):
    for i in range(1, 7):
        add_item(f"{i:03d}")
    for i in range(1, 6):
        client.post(f"/item/{i:03d}/star")
    with flask_app.app_context():
        assert db_module.count_starred() == 5
    client.post("/item/006/star")
    with flask_app.app_context():
        ids = {it["id"] for it in db_module.starred_items()}
        assert db_module.count_starred() == 5
        assert "006" in ids
        assert "001" not in ids


def test_starred_items_are_ordered_by_award_time(client, flask_app, add_item):
    for i in (3, 1, 2):
        add_item(f"{i:03d}")
    client.post("/item/003/star")
    client.post("/item/001/star")
    client.post("/item/002/star")
    with flask_app.app_context():
        assert [it["id"] for it in db_module.starred_items()] == ["003", "001", "002"]


def test_re_starring_an_already_starred_item_keeps_its_timestamp(client, flask_app, add_item):
    add_item("001")
    client.post("/item/001/star")
    with flask_app.app_context():
        first = db_module.get_item("001")["starred_at"]
        db_module.set_star("001", True)  # award again — should be a no-op
        assert db_module.get_item("001")["starred_at"] == first


def test_star_survives_an_item_edit(client, flask_app, add_item):
    add_item("001")
    client.post("/item/001/star")
    client.post("/item/001/edit", data={"item_type": "hoodie", "color": ["black"]})
    with flask_app.app_context():
        assert db_module.get_item("001")["starred"] is True


def test_closet_pins_starred_section_and_does_not_duplicate(client, add_item):
    add_item("001", name="pinned piece")
    add_item("002", name="ordinary piece")
    client.post("/item/001/star")
    body = client.get("/").data.decode()
    assert "gold star" in body.lower()
    assert body.count("pinned piece") == 1
    assert "ordinary piece" in body
