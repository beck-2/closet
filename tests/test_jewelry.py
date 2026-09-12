# ABOUTME: Tests for jewelry's own subtype field and its reduced rating
# ABOUTME: fields (condition only, no comfort/fit/season).
from __future__ import annotations

import db as db_module


def test_jewelry_subtype_round_trips(client, flask_app, add_item):
    add_item("001", item_type="jewelry", jewelry_subtype="earrings")
    with flask_app.app_context():
        assert db_module.get_item("001")["jewelry_subtype"] == "earrings"


def test_non_jewelry_items_have_no_subtype(client, flask_app, add_item):
    add_item("001", item_type="top")
    with flask_app.app_context():
        assert db_module.get_item("001")["jewelry_subtype"] is None


def test_saving_a_jewelry_item_only_keeps_condition(client, flask_app, add_item):
    add_item("001", item_type="top")
    resp = client.post("/item/001/edit", data={
        "item_type": "jewelry",
        "jewelry_subtype": "necklace",
        "comfort": "3",
        "fit": "2",
        "condition": "1",
        "season": ["summer"],
    })
    assert resp.status_code == 302
    with flask_app.app_context():
        item = db_module.get_item("001")
    assert item["jewelry_subtype"] == "necklace"
    assert item["condition"] == 1
    assert item["comfort"] is None
    assert item["fit"] is None
    assert item["season"] == []


def test_switching_away_from_jewelry_drops_the_subtype(client, flask_app, add_item):
    add_item("001", item_type="jewelry", jewelry_subtype="ring")
    client.post("/item/001/edit", data={"item_type": "top", "condition": "2"})
    with flask_app.app_context():
        assert db_module.get_item("001")["jewelry_subtype"] is None


def test_add_form_offers_jewelry_subtypes(client):
    body = client.get("/add").data.decode()
    assert "earrings" in body and "necklace" in body


def test_add_form_offers_swimsuit_and_belt(client):
    body = client.get("/add").data.decode()
    assert ">swimsuit<" in body and ">belt<" in body


def test_add_form_offers_scarf(client):
    body = client.get("/add").data.decode()
    assert ">scarf<" in body


def test_item_view_shows_only_condition_for_jewelry(client, add_item):
    add_item("001", item_type="jewelry", jewelry_subtype="pin", comfort=None, fit=None, condition=2)
    body = client.get("/item/001").data.decode()
    assert "jewelry · pin" in body
    assert "Condition" in body
    assert "Comfort" not in body
    assert ">Fit<" not in body
