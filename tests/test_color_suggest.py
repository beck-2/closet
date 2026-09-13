# ABOUTME: Tests for the color-suggestion helper (nearest-swatch matching
# ABOUTME: on a cutout's non-transparent pixels) and its live-preview route.
from __future__ import annotations

import io

from PIL import Image

import app as app_module


def test_solid_color_cutout_is_detected():
    cutout = Image.new("RGBA", (40, 40), (224, 57, 62, 255))  # matches "red"
    assert app_module.suggest_colors_from_cutout(cutout) == ["red"]


def test_navy_is_detectable():
    cutout = Image.new("RGBA", (40, 40), (27, 42, 74, 255))  # exactly "navy"
    assert app_module.suggest_colors_from_cutout(cutout) == ["navy"]


def test_transparent_background_pixels_are_ignored():
    cutout = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
    # a small red "garment" against a fully transparent background
    for x in range(10, 30):
        for y in range(10, 30):
            cutout.putpixel((x, y), (224, 57, 62, 255))
    assert app_module.suggest_colors_from_cutout(cutout) == ["red"]


def test_fully_transparent_cutout_suggests_nothing():
    cutout = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
    assert app_module.suggest_colors_from_cutout(cutout) == []


def test_a_faint_second_color_does_not_make_the_list():
    cutout = Image.new("RGBA", (40, 40), (224, 57, 62, 255))  # mostly red
    cutout.putpixel((0, 0), (91, 154, 99, 255))  # one lone green pixel
    assert app_module.suggest_colors_from_cutout(cutout) == ["red"]


def test_a_substantial_second_color_does_make_the_list():
    cutout = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
    for x in range(40):
        for y in range(40):
            color = (224, 57, 62, 255) if y < 20 else (91, 154, 99, 255)
            cutout.putpixel((x, y), color)
    assert app_module.suggest_colors_from_cutout(cutout) == ["red", "green"]


def test_multicolor_is_never_suggested_directly():
    assert not any(name == "multicolor" for name, _ in app_module._SWATCH_RGB)


# ------------------------------------------------------------------ route --

def _real_png_bytes() -> io.BytesIO:
    buf = io.BytesIO()
    Image.new("RGB", (20, 20), (0, 0, 0)).save(buf, format="PNG")
    buf.seek(0)
    return buf


def test_route_returns_suggested_colors(client, monkeypatch):
    monkeypatch.setattr("pipeline.process_images.get_session", lambda: object())
    fake_cutout = Image.new("RGBA", (10, 10), (224, 57, 62, 255))
    monkeypatch.setattr(
        "pipeline.process_images.cutout_from_image", lambda raw, session: fake_cutout
    )
    resp = client.post(
        "/add/suggest-colors",
        data={"photo": (_real_png_bytes(), "test.png")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    assert resp.get_json()["colors"] == ["red"]


def test_route_with_no_photo_returns_an_empty_list(client):
    resp = client.post("/add/suggest-colors", data={}, content_type="multipart/form-data")
    assert resp.status_code == 200
    assert resp.get_json()["colors"] == []


def test_route_with_unreadable_bytes_returns_an_empty_list(client):
    resp = client.post(
        "/add/suggest-colors",
        data={"photo": (io.BytesIO(b"not-a-real-image"), "test.png")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    assert resp.get_json()["colors"] == []


def test_route_swallows_a_background_removal_failure(client, monkeypatch):
    monkeypatch.setattr("pipeline.process_images.get_session", lambda: object())

    def _boom(raw, session):
        raise RuntimeError("model exploded")

    monkeypatch.setattr("pipeline.process_images.cutout_from_image", _boom)
    resp = client.post(
        "/add/suggest-colors",
        data={"photo": (_real_png_bytes(), "test.png")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    assert resp.get_json()["colors"] == []
