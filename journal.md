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

## Outstanding (step 4, not done — for later)
- BUG: templates/outfits_list.html checks `piece.images` but
  `_outfit_render_pieces` returns `.src` — saved-outfit thumbnails render as
  empty boxes. One-liner fix + test.
- requirements.txt is all `>=`, no lockfile — pin for reproducible installs.
- /photos and /originals have no Cache-Control (only /thumbs does).
- Naive `datetime.now()` for outfit created_at.
- No prod server story (app.run only) — waitress is a 1-liner if ever needed.
