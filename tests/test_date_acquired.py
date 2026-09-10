# ABOUTME: Tests for the flexible "date acquired" field — year-only or
# ABOUTME: year+month, stored as "YYYY" / "YYYY-MM", old values still readable.
from __future__ import annotations

import app as app_module
import db as db_module


def _post_edit(client, item_id, **extra):
    data = {"item_type": "top", "color": ["black"]}
    data.update(extra)
    return client.post(f"/item/{item_id}/edit", data=data)


def test_year_only_is_stored_as_bare_year(client, flask_app, add_item):
    add_item("001")
    _post_edit(client, "001", date_acquired_year="2019")
    with flask_app.app_context():
        assert db_module.get_item("001")["date_acquired"] == "2019"


def test_year_and_month_stored_as_iso_month(client, flask_app, add_item):
    add_item("001")
    _post_edit(client, "001", date_acquired_year="2019", date_acquired_month="3")
    with flask_app.app_context():
        assert db_module.get_item("001")["date_acquired"] == "2019-03"


def test_month_without_year_is_ignored(client, flask_app, add_item):
    add_item("001", date_acquired="2019-03")
    _post_edit(client, "001", date_acquired_year="", date_acquired_month="7")
    with flask_app.app_context():
        assert db_module.get_item("001")["date_acquired"] is None


def test_acquired_display_filter():
    f = app_module.app.jinja_env.filters["acquired_display"]
    assert f("2019-03") == "March 2019"
    assert f("2019") == "2019"
    assert f(None) == "—"
    assert f("") == "—"


def test_item_view_renders_month_name(client, add_item):
    add_item("001", date_acquired="2025-03")
    resp = client.get("/item/001")
    assert b"March 2025" in resp.data


def test_old_year_month_value_still_loads(client, add_item):
    add_item("001", date_acquired="2020-11")
    assert client.get("/item/001").status_code == 200
    assert b"November 2020" in client.get("/item/001").data


def test_edit_form_preselects_existing_year_and_month(client, add_item):
    add_item("001", date_acquired="2021-06")
    resp = client.get("/item/001/edit")
    assert b'value="2021" selected' in resp.data
    assert b'value="6" selected' in resp.data
