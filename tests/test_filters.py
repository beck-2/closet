# ABOUTME: Tests for the closet filter bar — the server side of it: the
# ABOUTME: per-card data attributes and the dropdown option lists.
from __future__ import annotations

import re


def test_cards_carry_all_filter_data_attributes(client, add_item):
    add_item(
        "001",
        name="Blue Winter Jacket",
        item_type="jacket",
        color=["blue", "black"],
        season=["winter"],
        source="thrifted",
        vibes=["Cozy", "Warm"],
    )
    body = client.get("/").data.decode()
    assert 'data-name="blue winter jacket"' in body
    assert 'data-type="jacket"' in body
    assert 'data-color="blue black"' in body
    assert 'data-season="winter"' in body
    assert 'data-source="thrifted"' in body
    assert 'data-vibes="cozy warm"' in body


def test_dropdowns_list_every_value_present(client, add_item):
    add_item("001", item_type="jacket", color=["blue"], season=["winter"], source="thrifted")
    add_item("002", item_type="dress", color=["red"], season=["summer"], source="gift")
    body = client.get("/").data.decode()
    for token in ("jacket", "dress", "blue", "red", "winter", "summer", "thrifted", "gift"):
        assert f'value="{token}"' in body


def test_filter_bar_controls_present(client, add_item):
    add_item("001")
    body = client.get("/").data.decode()
    assert 'id="filter-name"' in body
    assert 'id="filter-vibes"' in body
    for field in ("type", "color", "season", "source"):
        assert f'data-filter="{field}"' in body


def test_dropdown_options_are_sorted_and_deduped(client, add_item):
    add_item("001", color=["red", "blue"])
    add_item("002", color=["blue", "green"])
    body = client.get("/").data.decode()
    colors_section = body.split('data-filter="color"')[1].split("</select>")[0]
    values = [v for v in re.findall(r'<option value="([^"]*)"', colors_section) if v]
    assert values == ["blue", "green", "red"]
