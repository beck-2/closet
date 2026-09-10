# decisions

Why things are built the way they are. Newest first.

## Cached rembg session + on-disk thumbnails (2026-09-09)

**Session:** `add_item` / `edit_item` each called `rembg.new_session()` per
request — a multi-second load of the ~175MB model every single upload. Now
`pipeline.process_images.get_session()` builds it once per process and hands
the same session to every photo. The rembg import still lives inside a function
(`_new_session`) so importing the module doesn't pull in onnxruntime.

**Thumbnails:** the closet grid and outfit-builder tray were loading the full
1024px cutouts (~940 KB each, ~74 MB for the whole closet page). A new
`/thumbs/<name>` route serves a 400px cached copy from `data/thumbs/`,
regenerated whenever the source cutout is newer (so a touch-up shows through).
Closet page payload drops ~74 MB -> ~11 MB. 400px (not smaller) because the
grid renders ~200px cards and retina wants 2x.

**Why PNG, not WebP:** WebP would roughly halve the thumbs again, but means a
mislabeled extension or content negotiation. Left as a possible follow-up; the
6–7x win is already the bulk of it.

**Board pieces stay full-res:** the outfit builder can scale a piece up to
500px, so `trayitem[data-src]` still points at `/photos/` — only the visible
tray thumbnail uses `/thumbs/`.

## Test harness + configurable DB path (2026-09-09)

**What:** Added `pytest`, a `tests/` suite, and made the SQLite path come from
`app.config["DB_PATH"]` (overridable via the `CLOSET_DB_PATH` env var) instead
of a hardcoded module constant.

**Why:** `db.py` hardcoded `DB_PATH` and `app.py` called `db.init_db()` at
import time, so there was no way to point the app at a throwaway database for a
test. Threading a config value through `get_db()` / `init_db()` is the smallest
change that makes each test able to run against its own fresh temp DB.

**Why not a full `create_app()` factory / blueprint:** it would mean reindenting
every route and rewriting every `url_for()` in the templates (`closet` ->
`main.closet`). Big, risky diff for little gain right now. The config hook gets
us testable; we can promote to a real factory later if a step actually needs it.
