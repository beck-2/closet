# closet

digitizing my closet!

A personal digital wardrobe app — inspired by apps like Whering and Indyx, but
tailored to me: track every item, its condition, cost, and where I got it,
compute cost-per-wear, and save outfit combos.

## Status

**Phase 1 (in progress):** image pipeline — turn raw phone photos into clean,
consistent item images.

**Phase 2 (not started):** the actual closet app (browsing items, building
outfits, tracking wear/cost).

## Image pipeline

Raw phone photos (any aspect ratio, including iPhone `.HEIC`) go in
`data/raw/`. The pipeline:

1. Fixes rotation (EXIF orientation from the phone).
2. Removes the background, producing a transparent cutout.
3. Resizes so the longest edge is 1024px, keeping the original aspect ratio
   (never upscales).
4. Saves as a PNG (with alpha) into `data/processed/`.

Photos themselves aren't committed to git (see `.gitignore`) — this repo only
tracks the code that processes them.

### Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Run

```bash
python -m pipeline.process_images --input data/raw --output data/processed
```

Options:

- `--overwrite` — reprocess files even if an output already exists (by
  default, already-processed files are skipped so you can safely re-run this
  as you add new photos).
- `-v` / `--verbose` — more detailed logging.

Config knobs (target resolution, rembg model choice, output format) live in
`pipeline/config.py`.

First run downloads the background-removal model (~175MB) and caches it in
`~/.rembg/`, so it's slow once and fast after that.
