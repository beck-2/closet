# ABOUTME: Tests for the analytics dashboard — the aggregate numbers and
# ABOUTME: the collapsible money section.
from __future__ import annotations

import datetime

import db as db_module


def test_stats_page_renders_empty(client):
    resp = client.get("/stats")
    assert resp.status_code == 200
    assert b"by the numbers" in resp.data


def test_colour_donut_counts_each_colour_on_an_item(client, add_item):
    add_item("001", color=["blue", "black"])
    add_item("002", color=["blue"])
    body = client.get("/stats").data.decode()
    # blue appears on 2 items, black on 1 — legend shows both with counts
    assert "blue <b>2</b>" in body
    assert "black <b>1</b>" in body


def test_type_and_source_breakdowns(client, add_item):
    add_item("001", item_type="tshirt", source="thrifted")
    add_item("002", item_type="tshirt", source="new")
    add_item("003", item_type="pants", source="thrifted")
    body = client.get("/stats").data.decode()
    assert "thrifted" in body and "new" in body and "pants" in body


def test_most_worn_lists_items_by_wear_count(client, flask_app, add_item):
    add_item("001", name="daily driver")
    add_item("002", name="sometimes")
    with flask_app.app_context():
        db_module.log_items_worn("2026-09-01", ["001"])
        db_module.log_items_worn("2026-09-02", ["001"])
        db_module.log_items_worn("2026-09-03", ["002"])
    body = client.get("/stats").data.decode()
    # "daily driver" (2×) comes before "sometimes" (1×)
    assert body.index("daily driver") < body.index("sometimes")
    assert "2×" in body


def test_money_section_totals(client, flask_app, add_item):
    add_item("001", price=100.0)
    add_item("002", price=50.0)
    add_item("003", price=None)
    with flask_app.app_context():
        db_module.log_items_worn("2026-09-01", ["001"])
        db_module.log_items_worn("2026-09-02", ["001"])
    body = client.get("/stats").data.decode()
    assert "$150" in body                    # total spent
    assert "across 2 priced pieces" in body
    assert "$50.00" in body                   # blended cost per wear: $100 / 2 wears


def test_best_value_and_regrets(client, flask_app, add_item):
    add_item("001", name="great buy", price=20.0)
    add_item("002", name="the regret", price=200.0)
    with flask_app.app_context():
        for d in ("2026-09-01", "2026-09-02", "2026-09-03", "2026-09-04"):
            db_module.log_items_worn(d, ["001"])
    body = client.get("/stats").data.decode()
    assert "great buy" in body and "$5.00/wear" in body   # 20 / 4
    assert "the regret" in body and "$200" in body        # priced, never worn


def test_money_section_is_a_closed_details_by_default(client, add_item):
    add_item("001", price=10.0)
    body = client.get("/stats").data.decode()
    assert '<details class="moneysection"' in body
    assert "<details open" not in body


def test_item_page_shows_last_worn(client, flask_app, add_item):
    add_item("001")
    with flask_app.app_context():
        db_module.log_items_worn("2026-09-08", ["001"])
    body = client.get("/item/001").data.decode()
    assert "last worn Sep 8, 2026" in body


def test_utilisation_windows(client, flask_app, add_item):
    add_item("001")
    add_item("002")
    with flask_app.app_context():
        db_module.log_items_worn(datetime.date.today().isoformat(), ["001"])
    body = client.get("/stats").data.decode()
    assert "of 2 worn in the last 30 days" in body
    assert "of 2 worn in the last 90 days" in body
