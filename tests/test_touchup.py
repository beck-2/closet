# ABOUTME: Tests for the photo touch-up tool — the raw-photo endpoint the
# ABOUTME: "restore" brush paints from, and the page's guard rails.
from __future__ import annotations

import io

import pytest
from PIL import Image

import app as app_module


@pytest.fixture
def photo_on_disk(data_dir, monkeypatch):
    """A processed cutout (400x300) and a bigger raw photo (2000x1500) for
    item 001, with the app's BASE_DIR pointed at the temp data root."""
    monkeypatch.setattr(app_module, "BASE_DIR", data_dir.parent)
    Image.new("RGBA", (400, 300), (0, 0, 0, 0)).save(data_dir / "processed" / "001.png")

    def add_raw():
        Image.new("RGB", (2000, 1500), (180, 140, 90)).save(data_dir / "raw" / "001.jpeg")

    return add_raw


def test_raw_endpoint_returns_image_sized_to_the_cutout(client, photo_on_disk, add_item):
    photo_on_disk()
    add_item("001", images=["data/processed/001.png"], raw_images=["data/raw/001.jpeg"])
    with client.get("/item/001/photo/0/raw") as resp:
        assert resp.status_code == 200
        assert resp.mimetype == "image/jpeg"
        with Image.open(io.BytesIO(resp.data)) as im:
            assert im.size == (400, 300)  # resized to match the processed cutout


def test_raw_endpoint_404s_when_there_is_no_raw_on_file(client, photo_on_disk, add_item):
    add_item("001", images=["data/processed/001.png"], raw_images=[None])
    with client.get("/item/001/photo/0/raw") as resp:
        assert resp.status_code == 404


def test_raw_endpoint_404s_on_bad_index(client, photo_on_disk, add_item):
    photo_on_disk()
    add_item("001", images=["data/processed/001.png"], raw_images=["data/raw/001.jpeg"])
    with client.get("/item/001/photo/5/raw") as resp:
        assert resp.status_code == 404


def test_touchup_page_offers_restore_when_a_raw_exists(client, photo_on_disk, add_item):
    photo_on_disk()
    add_item("001", images=["data/processed/001.png"], raw_images=["data/raw/001.jpeg"])
    body = client.get("/item/001/photo/0/touchup").data.decode()
    assert 'data-mode="restore"' in body
    assert 'id="rawSrc"' in body
    assert "/item/001/photo/0/raw" in body


def test_touchup_page_disables_restore_without_a_raw(client, photo_on_disk, add_item):
    add_item("001", images=["data/processed/001.png"], raw_images=[None])
    body = client.get("/item/001/photo/0/touchup").data.decode()
    assert 'data-mode="restore"' in body and "disabled" in body
    assert 'id="rawSrc"' not in body


def test_touchup_page_offers_restore_original_when_a_raw_exists(client, photo_on_disk, add_item):
    photo_on_disk()
    add_item("001", images=["data/processed/001.png"], raw_images=["data/raw/001.jpeg"])
    body = client.get("/item/001/photo/0/touchup").data.decode()
    assert 'id="restoreOriginalBtn"' in body
    # The button itself shouldn't carry a "disabled" attribute when a raw
    # photo is on file — check the tag, not just page-wide text, since the
    # word "disabled" also appears (legitimately) on the paint-back button
    # in the no-raw case tested above.
    tag_start = body.index('id="restoreOriginalBtn"')
    tag = body[body.rindex("<button", 0, tag_start):body.index(">", tag_start)]
    assert "disabled" not in tag


def test_touchup_page_disables_restore_original_without_a_raw(client, photo_on_disk, add_item):
    add_item("001", images=["data/processed/001.png"], raw_images=[None])
    body = client.get("/item/001/photo/0/touchup").data.decode()
    tag_start = body.index('id="restoreOriginalBtn"')
    tag = body[body.rindex("<button", 0, tag_start):body.index(">", tag_start)]
    assert "disabled" in tag
