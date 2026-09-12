# ABOUTME: Tests for the drag-to-rearrange closet order — the sort_order
# ABOUTME: column, its persistence, and the save endpoint.
from __future__ import annotations

import db as db_module


def test_unordered_items_fall_back_to_id_order(client, flask_app, add_item):
    add_item("003")
    add_item("001")
    add_item("002")
    with flask_app.app_context():
        assert list(db_module.load_items()) == ["001", "002", "003"]


def test_set_closet_order_puts_items_in_that_order(client, flask_app, add_item):
    for i in ("001", "002", "003"):
        add_item(i)
    with flask_app.app_context():
        db_module.set_closet_order(["003", "001", "002"])
        assert list(db_module.load_items()) == ["003", "001", "002"]


def test_ordered_items_come_before_never_dragged_ones(client, flask_app, add_item):
    for i in ("001", "002", "003", "004"):
        add_item(i)
    with flask_app.app_context():
        db_module.set_closet_order(["003", "001"])  # 002 and 004 never placed
        assert list(db_module.load_items()) == ["003", "001", "002", "004"]


def test_order_survives_an_item_edit(client, flask_app, add_item):
    for i in ("001", "002"):
        add_item(i)
    with flask_app.app_context():
        db_module.set_closet_order(["002", "001"])
    client.post("/item/002/edit", data={"item_type": "hoodie", "color": ["black"]})
    with flask_app.app_context():
        assert list(db_module.load_items()) == ["002", "001"]


def test_save_order_endpoint(client, flask_app, add_item):
    for i in ("001", "002", "003"):
        add_item(i)
    resp = client.post("/closet/order", json={"order": ["002", "003", "001"]})
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True
    with flask_app.app_context():
        assert list(db_module.load_items()) == ["002", "003", "001"]


def test_save_order_endpoint_rejects_a_bad_payload(client):
    assert client.post("/closet/order", json={"order": "nope"}).status_code == 400
    assert client.post("/closet/order", json={}).status_code == 400
    assert client.post("/closet/order", json={"order": [1, 2, 3]}).status_code == 400


def test_closet_page_renders_cards_in_saved_order(client, flask_app, add_item):
    add_item("001", name="aay")
    add_item("002", name="bee")
    add_item("003", name="cee")
    with flask_app.app_context():
        db_module.set_closet_order(["003", "002", "001"])
    body = client.get("/").data.decode()
    assert body.index(">cee<") < body.index(">bee<") < body.index(">aay<")


# --------------------------------------- jewelry/shoes/accessories sort last --

def test_non_clothing_types_sort_after_clothes_by_default(client, flask_app, add_item):
    add_item("001", item_type="jewelry")
    add_item("002", item_type="top")
    add_item("003", item_type="shoes")
    add_item("004", item_type="hoodie")
    add_item("005", item_type="accessory")
    add_item("006", item_type="belt")
    add_item("007", item_type="swimsuit")
    with flask_app.app_context():
        # ids interleaved on purpose — clothes (002, 004, 007) first in id
        # order, then the non-clothing types (001, 003, 005, 006) in id
        # order. Swimsuit is clothing, so it stays with the clothes; belt
        # joins jewelry/shoes/accessory since it's an accessory too.
        assert list(db_module.load_items()) == ["002", "004", "007", "001", "003", "005", "006"]


def test_non_clothing_types_still_sort_after_clothes_even_when_dragged_first(client, flask_app, add_item):
    add_item("001", item_type="jewelry")
    add_item("002", item_type="top")
    with flask_app.app_context():
        # Explicitly place the jewelry item first — the category boundary
        # wins anyway; dragging can only reorder within a group.
        db_module.set_closet_order(["001", "002"])
        assert list(db_module.load_items()) == ["002", "001"]
