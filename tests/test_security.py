# ABOUTME: Tests for cross-site write protection and input hardening —
# ABOUTME: Origin/Referer checks on writes, and outfit payload validation.
from __future__ import annotations

import db as db_module

SELF_ORIGIN = "http://localhost"


def test_get_is_never_blocked_by_origin(client, add_item):
    add_item("001")
    resp = client.get("/", headers={"Origin": "http://evil.example"})
    assert resp.status_code == 200


def test_cross_site_form_post_is_forbidden(client, add_item):
    add_item("001")
    resp = client.post("/item/001/worn", headers={"Origin": "http://evil.example"})
    assert resp.status_code == 403
    with client.application.app_context():
        assert db_module.get_item("001")["wear_count"] == 0


def test_cross_site_json_post_is_forbidden(client, add_item):
    add_item("001")
    resp = client.post(
        "/outfits",
        json={"items": [{"id": "001", "x": 1, "y": 2, "w": 100, "rot": 0}]},
        headers={"Origin": "http://evil.example"},
    )
    assert resp.status_code == 403


def test_same_origin_post_is_allowed(client, add_item):
    add_item("001")
    resp = client.post(
        "/item/001/worn",
        headers={"Origin": SELF_ORIGIN},
    )
    assert resp.status_code == 302
    with client.application.app_context():
        assert db_module.get_item("001")["wear_count"] == 1


def test_cross_site_referer_is_forbidden_when_no_origin(client, add_item):
    add_item("001")
    resp = client.post("/item/001/worn", headers={"Referer": "http://evil.example/x"})
    assert resp.status_code == 403


def test_headerless_post_still_works(client, add_item):
    # The Flask test client (and curl) send neither header; a browser always
    # sends at least one. Header-less writes stay allowed so local tooling
    # and tests keep working.
    add_item("001")
    resp = client.post("/item/001/worn")
    assert resp.status_code == 302


# ------------------------------------------------------ outfit payloads --

def test_malformed_placement_is_400_not_500(client, add_item):
    add_item("001")
    resp = client.post("/outfits", json={"items": [{"id": "001", "x": 1}]})  # missing y/w/rot
    assert resp.status_code == 400
    assert resp.get_json()["ok"] is False


def test_non_numeric_placement_is_400(client, add_item):
    add_item("001")
    resp = client.post("/outfits", json={
        "items": [{"id": "001", "x": "left", "y": 2, "w": 100, "rot": 0}],
    })
    assert resp.status_code == 400
