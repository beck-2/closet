# ABOUTME: Route-level tests for the Flask app — rendering, validation,
# ABOUTME: redirects, JSON outfit endpoints, and the upload size guard.
from __future__ import annotations

import io

import db as db_module


# --------------------------------------------------------------- closet --

def test_index_lists_items(client, add_item):
    add_item("001", name="cozy longsleeve")
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"cozy longsleeve" in resp.data


def test_index_renders_all_items_filtering_is_client_side(client, add_item):
    add_item("001", item_type="top", name="a-top")
    add_item("002", item_type="shoes", name="z-shoes")
    resp = client.get("/")
    # Every card is in the HTML; the filter dropdowns narrow it in the browser.
    assert b"z-shoes" in resp.data
    assert b"a-top" in resp.data
    assert b'data-filter="type"' in resp.data


def test_item_view_and_404(client, add_item):
    add_item("001", name="the piece")
    assert client.get("/item/001").status_code == 200
    assert client.get("/item/999").status_code == 404


def test_mark_worn_increments_and_redirects(client, flask_app, add_item):
    add_item("001", wear_count=2)
    resp = client.post("/item/001/worn")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/item/001")
    with flask_app.app_context():
        assert db_module.get_item("001")["wear_count"] == 3


def test_mark_worn_missing_item_404(client):
    assert client.post("/item/999/worn").status_code == 404


# ------------------------------------------------------------- add/edit --

def test_add_form_renders(client):
    assert client.get("/add").status_code == 200


def test_add_without_photo_is_400(client):
    resp = client.post("/add", data={"item_type": "top"})
    assert resp.status_code == 400
    assert b"choose a photo" in resp.data


def test_add_with_photo_happy_path(client, flask_app, monkeypatch):
    monkeypatch.setattr("pipeline.process_images.get_session", lambda: object())
    monkeypatch.setattr(
        "app.process_upload",
        lambda file_storage, stub, session: (f"data/raw/{stub}.jpeg", f"data/processed/{stub}.png"),
    )
    data = {
        "item_type": "top",
        "color": ["black"],
        "photo": (io.BytesIO(b"not-a-real-image"), "shirt.jpg"),
    }
    resp = client.post("/add", data=data, content_type="multipart/form-data")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/item/001")
    with flask_app.app_context():
        item = db_module.get_item("001")
    assert item["item_type"] == "top"
    assert item["images"] == ["data/processed/001.png"]


def test_edit_form_renders(client, add_item):
    add_item("001")
    assert client.get("/item/001/edit").status_code == 200


def test_edit_removing_last_photo_is_rejected(client, flask_app, add_item):
    add_item("001", images=["data/processed/001.png"], raw_images=["data/raw/001.jpeg"])
    resp = client.post("/item/001/edit", data={
        "delete_image": "data/processed/001.png",
        "item_type": "top",
    })
    assert resp.status_code == 400
    assert b"at least one photo" in resp.data
    with flask_app.app_context():
        assert db_module.get_item("001")["images"] == ["data/processed/001.png"]


def test_edit_updates_fields(client, flask_app, add_item):
    add_item("001", name="old name")
    resp = client.post("/item/001/edit", data={
        "name": "new name",
        "item_type": "hoodie",
        "color": ["green"],
        "comfort": "3",
    })
    assert resp.status_code == 302
    with flask_app.app_context():
        item = db_module.get_item("001")
    assert item["name"] == "new name"
    assert item["item_type"] == "hoodie"
    assert item["color"] == ["green"]


# ------------------------------------------------------------- outfits --

def test_outfits_list_renders(client):
    assert client.get("/outfits").status_code == 200


def test_outfit_builder_renders(client, add_item):
    add_item("001")
    assert client.get("/outfits/new").status_code == 200


def test_create_outfit_requires_items(client):
    resp = client.post("/outfits", json={"name": "empty", "items": []})
    assert resp.status_code == 400
    assert resp.get_json()["ok"] is False


def test_create_update_delete_outfit(client, flask_app, add_item):
    add_item("001")
    add_item("002")

    created = client.post("/outfits", json={
        "name": "look", "vibes": "going out",
        "items": [{"id": "001", "x": 5, "y": 6, "w": 200, "rot": 1.0}],
    })
    assert created.status_code == 200
    outfit_id = created.get_json()["id"]

    updated = client.post(f"/outfits/{outfit_id}", json={
        "name": "look v2",
        "items": [
            {"id": "001", "x": 5, "y": 6, "w": 200, "rot": 1.0},
            {"id": "002", "x": 9, "y": 9, "w": 150, "rot": 0.0},
        ],
    })
    assert updated.status_code == 200
    with flask_app.app_context():
        outfit = db_module.get_outfit(outfit_id)
    assert outfit["name"] == "look v2"
    assert len(outfit["layout"]) == 2

    deleted = client.post(f"/outfits/{outfit_id}/delete")
    assert deleted.status_code == 302
    with flask_app.app_context():
        assert db_module.get_outfit(outfit_id) is None


def test_outfit_missing_targets_404(client):
    assert client.get("/outfits/nope/edit").status_code == 404
    assert client.post("/outfits/nope").status_code == 404
    assert client.post("/outfits/nope/delete").status_code == 404


# --------------------------------------------------------------- limits --

def test_oversized_upload_rejected(client, flask_app):
    flask_app.config["MAX_CONTENT_LENGTH"] = 1024
    resp = client.post(
        "/add",
        data={"photo": (io.BytesIO(b"x" * 4096), "big.jpg")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 413
