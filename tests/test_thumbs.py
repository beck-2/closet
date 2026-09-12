# ABOUTME: Tests for the on-disk thumbnail cache that backs the grid views —
# ABOUTME: generation, size clamping, caching headers, and path safety.
from __future__ import annotations

import io
import os

import pytest
from PIL import Image

import app as app_module


@pytest.fixture
def processed_png(tmp_path, monkeypatch):
    """Point the app's photo dirs at a temp location holding one 1000x800 PNG."""
    processed = tmp_path / "processed"
    thumbs = tmp_path / "thumbs"
    processed.mkdir()
    monkeypatch.setattr(app_module, "PROCESSED_DIR", processed)
    monkeypatch.setattr(app_module, "THUMBS_DIR", thumbs)
    Image.new("RGBA", (1000, 800), (120, 90, 200, 255)).save(processed / "001.png")
    return processed / "001.png"


def test_thumb_is_generated_and_downscaled(client, processed_png):
    with client.get("/thumbs/001.png") as resp:
        assert resp.status_code == 200
        assert resp.mimetype == "image/png"
        with Image.open(io.BytesIO(resp.data)) as im:
            assert max(im.size) == app_module.THUMB_LONG_EDGE
            assert im.size == (app_module.THUMB_LONG_EDGE, int(app_module.THUMB_LONG_EDGE * 0.8))


def test_thumb_sets_a_long_cache_header(client, processed_png):
    with client.get("/thumbs/001.png") as resp:
        assert "max-age=" in resp.headers.get("Cache-Control", "")


def test_thumb_is_cached_on_disk(client, processed_png):
    with client.get("/thumbs/001.png"):
        pass
    assert (app_module.THUMBS_DIR / "001.png").is_file()


def test_thumb_regenerates_when_source_is_newer(client, processed_png):
    with client.get("/thumbs/001.png"):
        pass
    thumb = app_module.THUMBS_DIR / "001.png"
    first_mtime = thumb.stat().st_mtime
    Image.new("RGBA", (1000, 800), (10, 10, 10, 255)).save(processed_png)
    os.utime(processed_png, (first_mtime + 10, first_mtime + 10))
    with client.get("/thumbs/001.png"):
        pass
    assert thumb.stat().st_mtime > first_mtime


def test_missing_source_is_404(client, processed_png):
    with client.get("/thumbs/nope.png") as resp:
        assert resp.status_code == 404


def test_thumb_path_traversal_is_blocked(client, processed_png):
    with client.get("/thumbs/..%2f..%2fapp.py") as resp:
        assert resp.status_code == 404


# ---------------------------------------------- thumb_url cache-busting --
# The 30-day Cache-Control header above means a browser that already has a
# /thumbs/<file> URL cached will keep showing that exact image for 30 days —
# it never even asks the server again. Since a touch-up rewrites the file at
# that same path/filename, the URL itself has to change when the content
# does, or the closet grid (and every other page using thumb_url) keeps
# showing the pre-touch-up thumbnail while the item page's own /photos/ URL
# (not cached this aggressively) shows the edit immediately — this was the
# reported bug.

def test_thumb_url_includes_a_cache_busting_version(flask_app, processed_png):
    with flask_app.test_request_context():
        url = app_module.thumb_url("data/processed/001.png")
    assert "/thumbs/001.png" in url
    assert "v=" in url


def test_thumb_url_changes_when_the_source_photo_changes(flask_app, processed_png):
    with flask_app.test_request_context():
        before = app_module.thumb_url("data/processed/001.png")
    mtime = processed_png.stat().st_mtime
    os.utime(processed_png, (mtime + 10, mtime + 10))
    with flask_app.test_request_context():
        after = app_module.thumb_url("data/processed/001.png")
    assert before != after


def test_thumb_url_survives_a_missing_source(flask_app, processed_png):
    with flask_app.test_request_context():
        url = app_module.thumb_url("data/processed/does-not-exist.png")
    assert "/thumbs/does-not-exist.png" in url


def test_closet_page_thumb_src_changes_after_a_touch_up(client, flask_app, processed_png, add_item):
    add_item("001", images=["data/processed/001.png"])
    before = client.get("/").data.decode()
    before_start = before.index('src="/thumbs/001.png')
    before_src = before[before_start:before.index('"', before_start + 5) + 1]

    mtime = processed_png.stat().st_mtime
    os.utime(processed_png, (mtime + 10, mtime + 10))

    after = client.get("/").data.decode()
    after_start = after.index('src="/thumbs/001.png')
    after_src = after[after_start:after.index('"', after_start + 5) + 1]

    assert before_src != after_src
