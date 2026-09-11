# closet

digitizing my closet!

A personal digital wardrobe app — inspired by apps like Whering and Indyx, but
tailored to me: track every item, its condition, cost, and where I got it,
compute cost-per-wear, and save outfit combos.

## Status

**Phase 1 (done):** image pipeline — turn raw phone photos into clean,
consistent item images.

**Phase 2 (in progress):** the actual closet app — browse items, view item
detail, build outfits with drag-and-drop, add new pieces. Metadata for each
item is still being filled in as you go (see `data/items.json`).

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

First run of anything that touches images downloads the background-removal
model (~175MB) and caches it, so it's slow once and fast after that.

## Running the app

```bash
source .venv/bin/activate
python app.py
```

Then open http://127.0.0.1:8000 in your browser. It's a local-only Flask app —
nothing leaves your machine.

- **Closet** — browse everything; filter by type / color / season / source
  (multi-select dropdowns), and search by name or vibe — search reorders the
  grid by relevance rather than hiding anything.
- Drag pieces around the closet grid to rearrange them — the order sticks.
- **Outfits** — build a look on a scrapbook-style board (drag pieces around,
  resize them, right-click to reorder), save it, and see saved outfits as
  little arranged boards. Click one to reopen it; hit **manage** to delete.
- **Calendar** — log what you wore each day: drag loose pieces onto a board
  (the same drag/resize/right-click editor as the outfit builder), and/or
  log a whole saved outfit; any past day. The month grid shows each day as
  one standard-size arranged board, and every item's wear count /
  cost-per-wear comes straight from the log. Open a day to optionally rate
  how it felt (1–3) and jot a note.
- **Stats** — colour / type / source breakdowns, what's actually in
  rotation, most-worn pieces, and a collapsible money section (total spent,
  cost per wear, best value, closet regrets).
- **+ Add Item** — upload a new photo; it runs through the same
  background-removal + resize pipeline automatically and gets the next item
  ID. The photo **touch-up** tool can erase stray background *or* paint a
  wrongly-removed part (a sleeve, a hem) back in from the original photo.
- Every item page has an **Edit item** button and a **Worn today** button
  (logs today on the calendar).
- "Date acquired" takes a year on its own, or a year and month.

## Development

```bash
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

Tests run against a throwaway SQLite database per test (never `data/closet.db`).
The app's database location can be overridden with the `CLOSET_DB_PATH`
environment variable.

## Image pipeline (used automatically by "+ Add Item", or run by hand)

Raw phone photos (any aspect ratio, including iPhone `.HEIC`) go in
`data/raw/`. The pipeline:

1. Fixes rotation (EXIF orientation from the phone).
2. Removes the background, producing a transparent cutout.
3. Resizes so the longest edge is 1024px, keeping the original aspect ratio
   (never upscales).
4. Saves as a PNG (with alpha) into `data/processed/`.

Photos themselves aren't committed to git (see `.gitignore`) — this repo only
tracks the code that processes them.

To batch-process a folder by hand instead of using the app's upload form:

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

## Item metadata

`data/items.json` is the source of truth for every item's metadata — there's
no spreadsheet. `pipeline/metadata_schema.py` documents/controls the allowed
values (item types, sources, color/season suggestions) — edit those lists
there as your closet reveals categories you didn't expect. The app's Add/Edit
forms read straight from this file, so a new item type or source shows up in
the dropdowns the next time you restart the app.

`python3 -m pipeline.validate_metadata` flags items still missing required
fields.
