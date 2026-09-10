# journal

## 2026-09-09
- Walked the whole repo with Beck. Personal Flask wardrobe app, SQLite-backed,
  local-only. Assessed weaknesses across perf / stack / security.
- Biggest findings: rembg session reloaded per upload, no thumbnails (71MB of
  full-res PNGs hit every grid view), zero tests, no CSRF on POST endpoints.
- Plan: full sequence, my order — (1) test harness + light app factory,
  (2) perf: cached rembg session + thumbnails, (3) security: CSRF + upload
  limits, (4) cleanup. Check in with Beck at each step.
- Starting step 1. Going with a lightweight config-driven setup rather than a
  full blueprint refactor — keeps the diff small, gets us testable.
- Step 1 done. `db.py` DB path now comes from `app.config["DB_PATH"]` /
  `CLOSET_DB_PATH`; `init_db()` takes an optional path. Added `MAX_CONTENT_LENGTH`
  (25MB) while I was in there. 29 tests (db layer, routes, pipeline helpers),
  `filterwarnings = error` so output stays pristine. All green in 0.2s.
  Smoke-tested against the real DB too — `/` and `/outfits` still 200.
- Beck committed his outfit-editing feature himself (7fb8216) while I was
  untangling the tree. Re-applied step 1 clean on top → 2b415cf.
- Step 2 (perf) done, committed. Cached rembg session (was reloading the
  175MB model every upload). Thumbnail route: closet page went 74MB → 11MB
  of image transfer. Verified in the browser — grid + tray crisp, board
  pieces still full-res. 36 tests green.
- Noticed a pre-existing bug while in there: `outfits_list.html` checks
  `piece.images` but `_outfit_render_pieces` returns `.src` — so saved-outfit
  thumbnails render as empty boxes. NOT mine to fix under the perf task;
  flagged to Beck.
- Step 3 (security) done. Cross-site write guard (Origin/Referer check in
  before_request), Pillow pixel cap, outfit payload validation. Verified with
  curl (evil Origin → 403, same-origin → 302, headerless → 302) and clicked
  "Worn today" through the browser — works. 44 tests green.
- Lesson: I ran a curl POST against the REAL data/closet.db during testing and
  double-bumped item 001's wear_count. Caught it, reset to 0. For the browser
  check I copied the DB to a temp file and used CLOSET_DB_PATH. Do that from
  the start next time.
- Beck called it after step 3 — stopping here. Steps 1-3 committed
  (2b415cf, 4cfb35d, 3db1120), nothing pushed. 44 tests green.

## 2026-09-09 (later) — feature batch
- Beck handed over a 4-item todo list (see TODO.md): flexible date_acquired,
  gold stars, richer filters + name search, outfit board / outfits-list work.
- Items 4's drag/resize/reorder/auto-top all already exist in
  outfit_builder.html — need to verify, not build. The real work in #4 is the
  arranged-board thumbnail (supersedes the earlier outfits_list bug chip) and
  an edit/delete path from the outfits list.
- Asking clarifying questions before starting #2/#3/#4. Starting #1 (date)
  now since it's self-contained.
- Beck's answers: star cap → bump oldest; filter dropdowns → type/color/
  season/source, text search for name + vibes; outfit list → edit-mode
  toggle; year range → 2010..now.
- #1 done + committed. Two dropdowns, `acquired_display` Jinja filter.
  Verified end-to-end in browser (picked April 2022 → shows "April 2022").
- FOUND (out of scope, pre-existing): editing an item silently drops any
  color that isn't one of the checkbox suggestions — item 001's "grey"
  (note: not "gray") vanished on save because `color_other` never
  pre-fills current free-form colors. Worth a fix later. Added to TODO.
- #2 (gold stars) done + committed. New `starred_at` column via a real
  idempotent migration path (`_run_column_migrations`), tested against a
  copy of the live 74-item DB. `set_star` bumps the oldest at cap 5.
  Closet gets a pinned "★ gold stars" row. Verified in browser.
- Decision: a star is a plain form POST like "Worn today" (no JS), toggles,
  redirects back to the item. Survives item edits because save_item's
  UPDATE clause never names starred_at.
- #3 (filters) done + committed. Went client-side: server renders every
  card with data-* attrs + the dropdown option lists, JS filters live.
  Dropped the old server `?type=` param (updated the one test that used
  it). name + vibes are substring text search; type/color/season/source
  are dropdowns. Verified all paths in the browser.
- #4 (outfits) done + committed. Turns out the board already did
  everything Beck asked (drag/resize/right-click reorder/auto-top) — I
  drove it all in the browser to confirm, no code change. Real work was:
  the outfits-list thumbnail is now the actual arranged mini-board (was
  rendering empty boxes — the old `piece.images` bug), and an edit-mode
  toggle next to "+ new outfit" reveals per-card edit + delete.
- Verified end to end: built a fit in the builder, resized a piece, sent
  it to back, saved → the list thumbnail matched the arrangement exactly.
- ALL 4 TODO ITEMS DONE. 69 tests green.
- Follow-up from Beck: filter dropdowns → checkbox chips, multi-select
  within a group = OR ("from sat or bauer"). Done. Had to switch the card
  data-attrs from space-join to pipe-join because source values contain
  spaces ("from sat"). Verified OR-within / AND-across / clear-all in the
  browser. 71 tests.
- Follow-up 2: whole outfit card now links into the builder (the "✎ edit"
  button was redundant — dropped it). The list-page toggle is now "manage"
  and only reveals the delete button. Restructured card so the delete
  <form> is a sibling of the <a>, not nested. Verified: click card → builder
  with pieces placed; manage → delete buttons. 72 tests.
- Follow-up 3: Beck sent a screenshot — ~40 filter chips all visible was
  "totally overwhelming". Collapsed each facet into a dropdown button
  ("Type ▾") that opens a checkbox panel; still multi-select + OR, still
  instant. One panel at a time, outside-click/Esc closes, count badge on
  the button. Kept the same checkbox filtering JS underneath.
- Gotcha: `.filterdrop-panel { display: flex }` overrode the browser's
  `[hidden]{display:none}` so all panels showed open on load — needed an
  explicit `.filterdrop-panel[hidden] { display: none }`.

## Outstanding (step 4, not done — for later)
- BUG: templates/outfits_list.html checks `piece.images` but
  `_outfit_render_pieces` returns `.src` — saved-outfit thumbnails render as
  empty boxes. One-liner fix + test.
- requirements.txt is all `>=`, no lockfile — pin for reproducible installs.
- /photos and /originals have no Cache-Control (only /thumbs does).
- Naive `datetime.now()` for outfit created_at.
- No prod server story (app.run only) — waitress is a 1-liner if ever needed.
