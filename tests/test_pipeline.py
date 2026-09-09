# ABOUTME: Tests for the pure image-pipeline helpers — resize math and
# ABOUTME: source-file discovery — nothing that invokes the rembg model.
from __future__ import annotations

from pathlib import Path

from PIL import Image

from pipeline.process_images import (
    find_source_images,
    output_path_for,
    resize_preserving_aspect,
)


def test_resize_never_upscales():
    img = Image.new("RGBA", (300, 200))
    out = resize_preserving_aspect(img, 1024)
    assert out.size == (300, 200)


def test_resize_scales_longest_edge_and_keeps_aspect():
    img = Image.new("RGBA", (2048, 1024))
    out = resize_preserving_aspect(img, 1024)
    assert max(out.size) == 1024
    assert out.size == (1024, 512)


def test_output_path_maps_into_output_dir_with_png_suffix():
    src = Path("data/raw/039_2.jpeg")
    out = output_path_for(src, Path("data/raw"), Path("data/processed"))
    assert out == Path("data/processed/039_2.png")


def test_find_source_images_filters_by_extension(tmp_path):
    (tmp_path / "a.jpeg").write_bytes(b"")
    (tmp_path / "b.HEIC").write_bytes(b"")
    (tmp_path / "notes.txt").write_bytes(b"")
    found = {p.name for p in find_source_images(tmp_path)}
    assert found == {"a.jpeg", "b.HEIC"}
