#!/usr/bin/env python3
"""
Closet photo pipeline: raw phone photos -> background-removed, resized PNGs.

Usage:
    python -m pipeline.process_images --input data/raw --output data/processed
    python -m pipeline.process_images --input data/raw --output data/processed --overwrite
    python -m pipeline.process_images --input data/raw --output data/processed --workers 1

What it does to each photo:
    1. Reads it (including iPhone .HEIC files).
    2. Applies EXIF orientation so sideways/upside-down phone shots come out upright.
    3. Removes the background, producing a transparent cutout (RGBA).
    4. Resizes so the longest edge is TARGET_LONG_EDGE px, keeping the original
       aspect ratio (never upscales an already-smaller image).
    5. Saves as a PNG next to a matching name in the output folder.

Skips files that already have a processed output, unless --overwrite is passed,
so you can re-run this over and over as you add new photos.
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps

from .config import (
    OUTPUT_EXTENSION,
    REMBG_MODEL,
    SUPPORTED_INPUT_EXTENSIONS,
    TARGET_LONG_EDGE,
)

# Cap how many pixels Pillow will decode from any one image. Guards against a
# small, highly-compressed "decompression bomb" upload blowing up memory.
# 64MP clears current phone sensors with room to spare; Pillow raises
# DecompressionBombError past 2x this. Set here because every uploaded photo
# passes through this module, and it's a process-wide PIL setting.
Image.MAX_IMAGE_PIXELS = 64_000_000

log = logging.getLogger("closet.pipeline")

# The rembg session owns the loaded background-removal model (~175MB on
# disk, and not cheap to spin up). Build it once per process and hand the
# same one to every photo — see get_session().
_session = None


def _new_session(model: str):
    """Thin, monkeypatch-friendly wrapper. The rembg import stays in here so
    merely importing this module doesn't drag in onnxruntime."""
    from rembg import new_session

    return new_session(model)


def get_session():
    """The process-wide rembg session, built lazily on first use."""
    global _session
    if _session is None:
        _session = _new_session(REMBG_MODEL)
    return _session


def _register_heif_opener() -> None:
    """Let Pillow open .HEIC/.HEIF files straight off an iPhone."""
    try:
        import pillow_heif

        pillow_heif.register_heif_opener()
    except ImportError:
        log.warning(
            "pillow-heif not installed — .HEIC/.HEIF photos will fail to open. "
            "Run: pip install pillow-heif"
        )


@dataclass(frozen=True)
class ProcessResult:
    source: Path
    output: Path
    status: str  # "ok" | "skipped" | "error"
    detail: str = ""


def find_source_images(input_dir: Path) -> list[Path]:
    return sorted(
        p
        for p in input_dir.rglob("*")
        if p.is_file() and p.suffix.lower() in SUPPORTED_INPUT_EXTENSIONS
    )


def output_path_for(source: Path, input_dir: Path, output_dir: Path) -> Path:
    rel = source.relative_to(input_dir).with_suffix(OUTPUT_EXTENSION)
    return output_dir / rel


def resize_preserving_aspect(img: Image.Image, target_long_edge: int) -> Image.Image:
    width, height = img.size
    long_edge = max(width, height)
    if long_edge <= target_long_edge:
        return img  # never upscale
    scale = target_long_edge / long_edge
    new_size = (max(1, round(width * scale)), max(1, round(height * scale)))
    return img.resize(new_size, Image.LANCZOS)


def cutout_from_image(raw: Image.Image, session) -> Image.Image:
    """EXIF-orient, convert to RGBA, and remove the background — the same
    transform process_one() applies to a file on disk, exposed separately
    so an in-memory caller (e.g. a live color-suggestion preview that never
    writes anything to disk) can reuse it without going through a file."""
    from rembg import remove

    oriented = ImageOps.exif_transpose(raw).convert("RGBA")
    return remove(oriented, session=session)  # background -> transparent


def process_one(
    source: Path,
    input_dir: Path,
    output_dir: Path,
    session,
    overwrite: bool,
) -> ProcessResult:
    out_path = output_path_for(source, input_dir, output_dir)

    if out_path.exists() and not overwrite:
        return ProcessResult(source, out_path, "skipped", "already processed")

    try:
        with Image.open(source) as raw:
            cutout = cutout_from_image(raw, session)
            resized = resize_preserving_aspect(cutout, TARGET_LONG_EDGE)

            out_path.parent.mkdir(parents=True, exist_ok=True)
            resized.save(out_path, format="PNG")

        return ProcessResult(source, out_path, "ok")
    except Exception as exc:  # noqa: BLE001 — we want to keep the batch going
        return ProcessResult(source, out_path, "error", str(exc))


def run(input_dir: Path, output_dir: Path, overwrite: bool) -> list[ProcessResult]:
    _register_heif_opener()

    sources = find_source_images(input_dir)
    if not sources:
        log.warning("No supported images found under %s", input_dir)
        return []

    log.info("Found %d image(s) to process", len(sources))
    session = get_session()

    results = []
    try:
        from tqdm import tqdm

        iterator = tqdm(sources, unit="img")
    except ImportError:
        iterator = sources

    for source in iterator:
        result = process_one(source, input_dir, output_dir, session, overwrite)
        results.append(result)
        if result.status == "error":
            log.error("FAILED  %s -> %s", result.source, result.detail)
        elif result.status == "skipped":
            log.debug("SKIP    %s (%s)", result.source, result.detail)
        else:
            log.info("OK      %s -> %s", result.source, result.output)

    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", type=Path, default=Path("data/raw"), help="Folder of raw phone photos")
    parser.add_argument("--output", type=Path, default=Path("data/processed"), help="Where processed PNGs go")
    parser.add_argument("--overwrite", action="store_true", help="Reprocess files even if an output already exists")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    if not args.input.exists():
        log.error("Input folder does not exist: %s", args.input)
        return 1

    results = run(args.input, args.output, args.overwrite)

    ok = sum(1 for r in results if r.status == "ok")
    skipped = sum(1 for r in results if r.status == "skipped")
    errors = [r for r in results if r.status == "error"]

    log.info("Done: %d processed, %d skipped, %d failed", ok, skipped, len(errors))
    for r in errors:
        log.error("  %s: %s", r.source, r.detail)

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
