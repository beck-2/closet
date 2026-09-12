# decisions

Why things are built the way they are. Newest first.

## Touch-up: a one-click full restore, kept separate from Reset and Paint back (2026-09-12)

The touch-up page already had two ways to "undo" the AI's cutout mistakes —
Reset (back to the cutout as it looked when the page opened) and a "Restore"
brush (paints back small raw patches under the cursor). Neither actually
brings back the whole original photo, which is what Beck needed when rembg
mangles a piece badly rather than just missing a sleeve.

Added a third, distinct action — **Restore original** — that drops the whole
raw photo onto the canvas in one click and switches to Erase mode, rather
than folding this into Reset or the brush. Reset and Restore original answer
different questions ("undo what *I* just did" vs. "undo what the *AI* did"),
and collapsing them would mean losing one or the other. The old brush stays
too, since a small mis-cut is still faster to patch by hand than to redo the
whole photo — it's just relabeled "Paint back" so it doesn't share a name
with the new button while doing something completely different.

## Jewelry/shoes/accessories sort last, enforced in the query (2026-09-12)

Beck wants jewelry/shoes/accessories to always display after the clothes.
The obvious quick version would be a display-time sort in the template or
route. Instead the category boundary went into `db._ITEM_ORDER`'s `ORDER BY`
itself (a `CASE WHEN item_type IN (...) THEN 1 ELSE 0 END` ahead of the
existing `sort_order`/`id` clause) — every page that lists items
(`load_items()`) gets the same grouping for free, and dragging a jewelry
item earlier in the closet grid doesn't quietly stick past a reload. If the
sort had lived in one route instead, the outfit-builder and calendar trays
would've needed the same logic copy-pasted, and a drag that "worked" until
refresh would've been a confusing bug report waiting to happen.

**Jewelry's reduced fields are enforced server-side, not just hidden.**
`item_form.html`'s JS hides Comfort/Fit/Season when the item type is
jewelry, but a hidden `<input>`/`<select>` still submits whatever value it
last held — so `_read_form_item()` forces comfort/fit to `None` and season
to `[]` whenever `item_type == "jewelry"`, regardless of what the POST body
actually contains. The client-side toggle is just UX; the real rule lives
in the one function every save (add and edit) already runs through.

## Logging a day reuses the outfit builder itself (2026-09-11)

The month-grid mini-boards (previous entry below) fixed outfits, but loose
items logged for a day still showed as plain same-size squares next to them —
Beck: "still a little weird," and asked to just reuse the outfit builder so
every day is one standard-size board he can arrange however he wants.

**`static/js/board-editor.js`** is the outfit builder's drag/resize/right-click
engine, pulled out verbatim into a shared file rather than copy-pasted into
the calendar day page. `createBoardEditor(initialPieces)` owns the board DOM
and returns `{isEmpty, getPieces}`; each page keeps its own save button and
payload shape. One editor, two callers — a change to how dragging works only
needs to happen once. The board/tray CSS (`.board`, `.cutout`, `.traygrid`,
etc.) is now selector-shared between `.pg-outfits` and `.pg-calday` for the
same reason: it's the same visual thing in both places, not a look-alike.

**`day_layout`** is a new table, same shape as `outfit_items` (`x/y/w/rot`),
keyed by date instead of by outfit id — the day's own unnamed, non-reusable
arrangement. Saving it (`db.save_day_layout`) is now *also* how loose items
get logged or unlogged for that day: whatever's on the board when you hit
save is what's logged, full stop. That folded the separate checkbox tray,
the per-item remove button, and the item-id branch of `calendar_day_log`
into one mechanism.

**Auto-placement for already-logged, unpositioned items**
(`_day_board_pieces`): the item page's "Worn today" button logs an item with
no board position. Rather than rendering those separately (the old
inconsistency), the day board gives them a default staggered spot — same
math the JS uses when you drag a fresh piece in — so opening a day's board
always shows everything you've logged for it, never a silent gap.

**Month grid** collapsed to a flat list of "tiles" — each saved outfit plus
the day's ad-hoc board if it has anything on it — capped at 1 shown with a
"+N" badge, since every tile is now the same board shape and stacking more
than one starts hurting the grid's compactness more than it helps.

## Calendar: outfits as mini-boards, day notes separate from wear_log (2026-09-11)

Month-grid day cells previously flattened everything worn that day into a row
of same-size icons, with a logged outfit contributing only its first piece.
Now a logged outfit renders as the same absolutely-positioned mini-board used
in outfit_builder / outfits_list / the day-detail page — one visual language
for "an outfit" everywhere it appears. Loose items still get plain thumbnails,
just bigger (30px -> 46px) since that was the actual complaint (screenshot:
"you can hardly tell what item it is").

The per-day comfort rating + notes live in their own `day_log` table
(`worn_on` primary key), not on `wear_log` — they're a property of the day,
independent of what got logged as worn or later removed. Both fields are
optional; saving with neither set deletes the row rather than leaving an
empty one. Shown only on the day-detail page, which was already reached by
clicking a day — no new disclosure UI needed for "only when you click on that
day."

## No emojis, no instruction microcopy (2026-09-10)

Beck's standing rule for this app: no emojis in the UI (they read as
AI-generated), and no explanatory helper text ("drag pieces to rearrange",
"N items logged"). The UI should be intuitive on its own; ask before adding
any hint. Close/remove buttons use a plain `×` (U+00D7), not `✕`; carets use
`▾`. If an affordance seems genuinely non-obvious, raise it — don't paper
over it with microcopy.

## Analytics dashboard (2026-09-10)

A `/stats` page, three sections: Wardrobe (composition), Wear (usage), Money.

- **Charts are hand-rolled** — an SVG donut built from `stroke-dasharray`
  segments, bars are CSS-width divs. The app has zero JS dependencies and no
  build step; a chart library would be the first crack in that.
- **Money is a `<details>`** that starts closed; the open/closed choice is
  remembered in `localStorage` (a per-device convenience, not shared state).
  Closed-by-default so a glance at the screen doesn't show finances.
- **"Blended" avg cost-per-wear** = total spent on priced-and-worn pieces ÷
  their total wears, not the mean of per-item ratios (which a single
  worn-once expensive piece would dominate). Free ($0) pieces ARE counted in
  the average — a $0 gift you wear constantly genuinely lowers it — but are
  excluded from the "best value" ranking, where $0.00/wear isn't a story.
- Per-item cost-per-wear stays on the item page (it was already a stat card
  there); the dashboard is closet-wide aggregates only.

## Calendar & wear log (2026-09-09)

`wear_log` is the single source of truth for what was worn when. Shape: **one
row per garment worn**, with `outfit_id` set when that row came from logging a
whole outfit and NULL for a loose item. So:
- item wear count = `COUNT(*) FROM wear_log WHERE item_id = ?` — dead simple,
  and logging an outfit correctly counts a wear for each of its pieces.
- a day's outfits = `DISTINCT outfit_id` for that date; loose items = rows with
  NULL outfit_id.
- removing a logged outfit = delete that date's rows with that outfit_id.

`items.wear_count` is **retired** — `_item_from_row` derives it. The column
stays in the schema (the JSON import still writes it, harmless) but nothing
reads it. Beck had essentially no historical counts, so deriving lost nothing.

"Worn today" on the item page now inserts a wear_log row for today instead of
bumping a counter. Past days are backfillable; future days 404 / 400.

Jinja footgun met here: `{{ worn.items }}` resolves to the dict's `.items`
*method*, not the `"items"` key. The day route passes `worn_items` /
`worn_outfits` as separate template vars.

## Closet drag-to-reorder (2026-09-09)

`items.sort_order INTEGER`, nullable. `load_items()` orders
`sort_order IS NULL, sort_order, id` so hand-placed items come first and
anything never dragged trails behind by id — that's what keeps a brand-new
item at the end until you place it. `save_item`'s UPDATE never names
`sort_order`, so the order survives editing an item.

The drag is pointer-events based (not HTML5 DnD, not a library — consistent
with the outfit board). A 6px move threshold separates a drag from a click,
and a one-shot capture-phase `click` handler swallows the click that would
otherwise fire after a drag. `.dragging` gets `pointer-events: none` so
`elementFromPoint` can see the card being hovered *under* it.

It lives in the same IIFE as the filters so it shares `originalOrder`; after
a drop that array is rebuilt from the DOM, so clearing a search afterwards
restores the *new* order, not the pre-drag one. Dragging is disabled whenever
a filter or search is active — reordering only makes sense in the natural view.

## Touch-up tool: a "restore" brush, snapshot-based reset (2026-09-09)

The auto background-removal sometimes eats part of a garment (a grey sleeve on
a wood floor). The touch-up tool used to only erase, and its "Reset to
original" restored a `data/originals/` backup that, for older items, had been
captured lazily from disk *after* the damage — so reset did nothing useful.

Now:
- **Reset** reverts to a `getImageData` snapshot taken the moment the page
  loaded. Synchronous, always correct, no server round-trip.
- A **Restore brush** paints the garment back from the original uploaded
  photo. `/item/<id>/photo/<i>/raw` serves that photo EXIF-rotated and resized
  to exactly the cutout's dimensions, so `drawImage(raw, 0,0,w,h)` lines up.
  It paints the raw's background back too — you then switch to Erase to clean
  around the restored part. Predictable beats clever.
- The `data/originals/` backup machinery is gone — the raw photo is the real
  original, and the backup only ever confused the reset logic.

## Closet filters: collapsed multi-select dropdowns, OR within a facet (2026-09-09)

Type/color/season/source each become a small dropdown button ("Type ▾") that
opens a panel of checkboxes. Multi-select, applies instantly, and checking
several boxes in one facet **widens** the results (OR): "everything from sat
or bauer". Facets still narrow across each other (AND). A count badge on the
button shows how many are picked.

They were briefly ~40 always-visible chips (one click, very direct) but that
was visually overwhelming with a real closet's worth of values — the collapsed
dropdown keeps the same behaviour without the wall of buttons. Not a native
`<select multiple>` (unusable on most platforms) — a plain button + absolutely
positioned panel, one open at a time, closed by outside-click or Esc.

Watch out: a `.panel { display: flex }` rule beats the UA `[hidden]{display:none}`,
so the panel needs an explicit `[hidden]{display:none}` of its own or it renders
open on load. **The exact same trap hit `.pg-closet .card { display: block }`** —
the filter JS set `card.hidden` correctly but the card never hid, so filtering
looked completely broken. Any class that sets `display` AND gets toggled via the
`hidden` attribute needs its own `.thing[hidden] { display: none }`.

## Closet name/vibes search: rank, don't filter (2026-09-09)

Typing in the name or vibes box **reorders** the grid — matches float to the top
by relevance (exact 100 > starts-with 60 > word-starts-with 40 > contains 15),
ties keep their original order — and nothing is hidden. Clearing the box puts
every card back in its original (id) position. The checkbox dropdowns are what
actually filter (hide) the grid; text search only re-ranks what's visible.

## Gold stars: removed (2026-09-09)

Built (ece8f76) then pulled at Beck's request. The `starred_at` column is out of
the schema; databases that already have it (Beck's) keep the unused column rather
than eat a destructive `DROP COLUMN`. The one-off `_run_column_migrations` hook
went with it — no migrations remain and the pattern is in git history.

The card filter data-attributes are pipe-joined (`data-color="blue|black"`),
not space-joined, because some values legitimately contain spaces (`from sat`,
`from bauer`, `from mom`) and whitespace tokenising split them apart. `vibes`
stays space-joined — it's a substring search, not a token match.

A facet with no values across the whole closet renders no group at all.

## Cross-site write protection via Origin/Referer, not CSRF tokens (2026-09-09)

**What:** A `before_request` guard rejects any non-GET whose `Origin` (or,
absent that, `Referer`) names a host other than the one being served. A
request with neither header (curl, the test client, local scripts) passes.

**Why this and not Flask-WTF `CSRFProtect`:** the app has no login and no
sessions, so a CSRF token would just be a value the page hands back to itself.
The actual risk is a web page in the same browser POSTing to
`http://127.0.0.1:8000`. Browsers always attach `Origin` (or at least
`Referer`) to a state-changing request, and this check is the OWASP-endorsed
same-site defense. Token plumbing across 5 templates + 3 `fetch()` calls is a
lot of surface for a single-user localhost tool; this is one function.

**Why header-less requests are allowed:** anyone who can send a header-less
POST to localhost already runs code on the machine — not the threat model.
Keeping them allowed means tests and local scripts need no ceremony.

## Pixel cap + outfit payload validation (2026-09-09)

`Image.MAX_IMAGE_PIXELS = 64_000_000` in the pipeline module (process-wide,
and every upload goes through there) so a small highly-compressed
"decompression bomb" can't blow up memory. `_clean_placements()` coerces the
outfit board layout to exact types and returns a 400 on anything malformed,
instead of a `KeyError` 500 landing in the storage layer.

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
