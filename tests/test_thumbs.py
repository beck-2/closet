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
