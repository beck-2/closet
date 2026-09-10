# ABOUTME: Tests for the closet filter bar — the server side of it: the
# ABOUTME: per-card data attributes and the multi-select dropdown options.
from __future__ import annotations

import re


def test_cards_carry_all_filter_data_attributes(client, add_item):
    add_item(
        "001",
        name="Blue Winter Jacket",
        item_type="jacket",
        color=["blue", "black"],
        season=["winter"],
        source="from sat",
        vibes=["Cozy", "Warm"],
    )
    body = client.get("/").data.decode()
    assert 'data-name="blue winter jacket"' in body
    assert 'data-type="jacket"' in body
    assert 'data-color="blue|black"' in body        # pipe-joined: values can contain spaces
    assert 'data-season="winter"' in body
    assert 'data-source="from sat"' in body
    assert 'data-vibes="cozy warm"' in body


def test_each_facet_is_a_collapsed_dropdown_of_checkboxes(client, add_item):
    add_item("001", item_type="top", source="from sat")
    body = client.get("/").data.decode()
    assert "<select" not in body                       # not a native select
    assert 'class="filterdrop" data-group="type"' in body
    assert 'class="filterdrop-panel" hidden' in body   # panel starts closed
    assert 'type="checkbox" data-filter="type"' in body
    assert 'type="checkbox" data-filter="source"' in body


def test_every_present_value_gets_a_checkbox(client, add_item):
    add_item("001", item_type="jacket", color=["blue"], season=["winter"], source="from sat")
    add_item("002", item_type="dress", color=["red"], season=["summer"], source="from bauer")
    body = client.get("/").data.decode()
    for value in ("jacket", "dress", "blue", "red", "winter", "summer", "from sat", "from bauer"):
        assert f'value="{value}"' in body


def test_filter_bar_search_boxes_present(client, add_item):
    add_item("001", item_type="top", color=["black"], season=["summer"], source="thrifted")
    body = client.get("/").data.decode()
    assert 'id="filter-name"' in body
    assert 'id="filter-vibes"' in body
    for field in ("type", "color", "season", "source"):
        assert f'data-filter="{field}"' in body


def test_empty_facet_renders_no_dropdown(client, add_item):
    add_item("001", item_type="top", color=[], season=[], source="thrifted")
    body = client.get("/").data.decode()
    assert 'data-group="color"' not in body    # nothing has a color yet
    assert 'data-group="type"' in body


def test_checkbox_options_are_sorted_and_deduped(client, add_item):
    add_item("001", color=["red", "blue"])
    add_item("002", color=["blue", "green"])
    body = client.get("/").data.decode()
    color_values = re.findall(r'data-filter="color" value="([^"]*)"', body)
    assert color_values == ["blue", "green", "red"]


def test_cards_render_in_id_order(client, add_item):
    # This is the "normal position" the name/vibes search reorders away from
    # and restores to when cleared (the reordering itself is client-side).
    add_item("003", name="cee")
    add_item("001", name="aay")
    add_item("002", name="bee")
    body = client.get("/").data.decode()
    assert body.index(">aay<") < body.index(">bee<") < body.index(">cee<")
