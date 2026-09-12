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
- Follow-up 4: Beck says filtering "simply isn't working". Root cause: the
  SAME `[hidden]` trap on `.pg-closet .card { display:block }` — the filter
  JS set the attribute correctly the whole time (since item 3!) but the
  card never hid. My earlier "verification" checked `:not([hidden])` which
  counts the ATTRIBUTE, not rendered visibility — so I never caught it.
  Lesson: verify with getComputedStyle / eyeballs, not the attribute.
- Same follow-up: name/vibes search reworked from filter → ranking. Matches
  float up by relevance score, nothing hidden, clear restores id order.
- Same follow-up: removed gold stars entirely (Beck's call). Schema column
  gone; his existing DB keeps an unused starred_at column (harmless).
  Dropped _run_column_migrations too — no migrations left; pattern's in git
  history (ece8f76) if needed again.

## 2026-09-09 (batch 2) — drag-reorder, touch-up fix, calendar
- 3 new todos (TODO.md items 5/6/7). Beck: calendar logs both items AND
  outfits, backfill any past day, keep "Worn today" wired to it.
- #6 (touch-up) done first. The damaged items are the 3 UNNAMED ones
  (028/039/040) — rembg ate the sleeves against wood-floor backgrounds.
  Root cause of "restore doesn't work": the originals backup was captured
  lazily from disk on first touch-up open, so for these it was already the
  broken cutout. Fixed Reset to a synchronous page-load snapshot, added a
  Restore brush that paints back from the raw photo (new /photo/<i>/raw
  route, EXIF-rotated + resized to cutout dims). Verified on 028 in browser
  — painted the sleeve back. Removed the dead data/originals/ machinery.
  Beck will re-fix 028/039/040 himself with the new tool.
- #5 (drag-reorder closet) done. New sort_order column + ALTER migration
  (brought the column-check pattern back, inline in init_db this time).
  Pointer-based drag with a 6px click/drag threshold, merged into the
  filter IIFE so originalOrder stays in sync. Disabled while filtering.
  Verified real mouse drag + persist + click-navigation in the browser.
- #7 (calendar) done — the big one. New wear_log table (CREATE IF NOT
  EXISTS, no ALTER needed). Model: one row per piece worn, outfit_id set
  when it came from logging an outfit. wear_count is now DERIVED from
  wear_log — retired items.wear_count (kept in schema, unread; Beck had
  basically no historical counts so nothing lost). Month grid + day-detail
  pages, "Calendar" nav pill. "Worn today" logs into today. Backfill any
  past day; future days blocked. Jinja gotcha: `worn.items` resolves to
  dict.items() — passed worn_items/worn_outfits as separate vars.
  Fixed 3 wear_count tests for the derived model. Verified end to end in
  the browser (log items+outfit on Sept 8, month grid thumbnails, "Worn
  today" → Sept 9, remove).
- ALL 3 BATCH-2 TODOS DONE (#5 #6 #7). 86 tests.

## 2026-09-10 — analytics dashboard
- Brainstormed ~13 widgets, Beck picked a subset. Built /stats: Wardrobe
  (colour donut + type/source bars), Wear (rotation % + most-worn), Money
  (collapsed <details>, localStorage-remembered: total spent, blended CPW,
  best value, regrets). Hand-rolled SVG donut (stroke-dasharray segments) —
  no chart library, keeps the zero-dep setup.
- Item page: added "last worn <date>".
- Gotcha: filtered price=0 items out of "best value" (gifts showing $0/wear
  isn't a value story).
- Browser-pane screenshots were flaky mid-session (blank captures when
  hidden / after programmatic scroll) — verified layout via getBoundingClientRect
  + innerText instead, which was reliable.
- 95 tests.
- Beck review of the dashboard: NO EMOJIS in the UI (reads as AI-gen), and
  NO instructional helper text — asked me to remember both. Stripped all
  emojis app-wide (💰 🗑 ✎; ✕→×). Removed the grey hint lines: closet
  draghint, outfit-builder top hint + sidebar hint, stats "N pieces logged".
  Saved as a memory. Most-worn card: capped width, scrolls after ~5.
  Money section: solid border, title "PRICE" + caret, no show/hide button.
  Also: excluded $0 pieces from "best value" (a free gift at $0/wear isn't
  a value story) — avg CPW went $16.17 → $24.25.
- Beck follow-up: keep free items IN the average CPW (a $0 gift you wear a
  lot legitimately pulls your average down), just not in best value. Avg
  back to $16.17. Also removed the drop shadow from closet cards — flat now.

## Outstanding (step 4, not done — for later)
- BUG: templates/outfits_list.html checks `piece.images` but
  `_outfit_render_pieces` returns `.src` — saved-outfit thumbnails render as
  empty boxes. One-liner fix + test.
- requirements.txt is all `>=`, no lockfile — pin for reproducible installs.
- /photos and /originals have no Cache-Control (only /thumbs does).
- Naive `datetime.now()` for outfit created_at.
- No prod server story (app.run only) — waitress is a 1-liner if ever needed.

## 2026-09-11 — calendar polish
- Month grid: loose-item thumbs 30px -> 46px. Outfits now render as the
  arranged mini-board (same technique as outfits_list/day-detail) instead
  of just the first piece mixed into a flat row — this is what Beck's
  screenshot was actually complaining about (tiny, indistinguishable icons).
- Gotcha: called the day-info dict key "items" — collided with Python
  dict.items(), so Jinja's `info.items` resolved to the bound method, not
  the key, and crashed. Renamed to "loose_items".
- New optional per-day comfort rating (1-3 dots) + notes, `day_log` table.
  Lives only on the day-detail page (already gated behind clicking a day —
  no new "click to reveal" needed). "clear" link unchecks an accidental
  radio pick. Saving both blank deletes the row.
- The day-detail page already used the mini-board for logged outfits (built
  earlier) — verified, nothing to change there.
- 104 tests. Verified end-to-end in the browser against a copy of the real
  DB: Sept 8's 3-piece outfit renders as a proper arranged board, rated it
  3/3 with a note, reloaded and it stuck, cleared the rating.

## 2026-09-11 (later) — the day board
- Beck's reaction to the last screenshot: the loose-item squares were
  "still a little weird" next to the outfit board, and asked to just reuse
  the outfit builder itself for logging a day — uniform square, resize
  however he wants.
- Pulled the outfit builder's whole drag/resize/reorder engine out into
  static/js/board-editor.js (first static JS file in the app) so the day
  page and the outfit builder run the identical editor instead of two
  copies drifting apart. Broadened the shared board/tray CSS from
  `.pg-outfits` to also match `.pg-calday`.
- New day_layout table, shaped exactly like outfit_items, keyed by date
  instead of outfit id. Saving it now IS how you log/unlog loose items for
  a day — no more separate checkbox tray or per-item remove button.
  _day_board_pieces() auto-places anything logged-but-unpositioned (e.g.
  from the item page's quick "Worn today") so the board never silently
  drops something you've logged.
- Month grid simplified to a flat "tiles" list (outfits + the day's ad-hoc
  board), each tile the same board size, capped at 1 with a "+N" badge —
  replaces the earlier items-vs-outfits split rendering entirely.
- Rewrote tests/test_calendar.py around the new flow rather than patching —
  the old item_id-checkbox tests didn't map onto board semantics.
- Gotcha: a test asserting on `left: ` in the day page HTML passed for the
  wrong reason — that page renders the ad-hoc board client-side from JSON
  (no inline `style="left:..."` in the HTML at all), and "+2" showed up
  coincidentally from "Baloo+2" in the Google Fonts URL in <head>. Both
  were silently-passing tests that had stopped checking anything real.
  Rewrote them to assert on the actual JSON payload / exact tile count.
- 112 tests. Verified in the browser: measured all 4 month-grid boards at
  exactly 103x106px regardless of piece count; dragged a 3rd piece onto a
  day's board, saved, reloaded, confirmed day_layout + wear_log rows in
  the DB directly; outfit builder unchanged through the shared JS.

## 2026-09-11 (later still) — day-page polish
- Two quick Beck asks: (1) saving the day board should go back to the
  calendar, not reload the day; (2) drop the grey "what you wore" label.
- Did (1) properly rather than the literal minimum: redirect target is the
  day's own year/month (passed from the route as `calendar_url`), not
  always today's — otherwise editing a January day while looking at
  September would bounce you to September. Fixed the "← calendar" back
  chip the same way while in the file, since it had the identical bug.

## 2026-09-12 — aesthetics pass tried, then reverted
- Beck's ask: punk-cyber wordmark font, picture frames on closet items,
  and a sitewide pink-only accent color. Built all three (font gitignored
  for licensing — it's personal-use-only and the repo is public — with a
  README + fallback font so the app still works without the binary).
- Beck's call after seeing it: didn't like it, revert. Commit had never
  been pushed, so `git reset --hard` back to the prior commit was clean —
  no need for `git revert`. 113 tests still green after.

## 2026-09-12 (later) — add-item drag-and-drop, one calendar save button
- First pass at add-item drag-and-drop (dragover/drop listeners on the
  upload zone) tested fine via synthetic JS-dispatched events, but Beck
  reported it still didn't work with a real Finder/browser-tab drag.
  Root cause: `app.run(debug=False)` means Jinja's template auto-reload is
  off, so the running server was still serving the pre-fix compiled
  template — the fix never actually reached his browser. Needs a server
  restart (`python app.py`) to pick up template edits, not just a
  page reload; flagged this to Beck rather than guessing further.
- Calendar day page had three separate save buttons (board / log-outfit /
  notes), each its own `<form>` posting to a different route and bouncing
  back to the day page. Beck wants one button at the bottom for all of it.
  Kept the three backend routes as-is (already tested, independently
  useful) — stripped the `<form>`/button chrome around the outfit-select
  and notes/rating sections down to plain `<div>`s, and had the one
  remaining save button fire all three POSTs in sequence (board, then
  outfit if one's picked, then notes/rating), redirecting to the day's
  month grid only once all three land.
- 113 tests still passing (none were coupled to the removed form markup).
  Verified the merged save in the browser against a DB copy: picked an
  outfit, set a rating, typed a note, one click — all three landed in the
  DB (wear_log outfit row + day_log comfort/notes).

## 2026-09-12 (later still) — jewelry, shoes, accessories
- `jewelry`/`shoes`/`accessory` were already valid item_type values but got
  no special treatment. Beck wants them always after the clothes, jewelry
  with its own subtype + condition-only rating (no comfort/fit/season),
  shoes/accessories otherwise unchanged.
- Ordering: added a `CASE WHEN item_type IN (...)` to db._ITEM_ORDER so the
  category boundary is enforced in the query itself, not just a starting
  position — dragging a jewelry item earlier doesn't stick past a reload,
  which is what "always after" should mean. Single source (load_items())
  used by the closet grid, outfit-builder tray, and calendar-day tray
  alike, so all three stay consistent for free.
- New `items.jewelry_subtype` column, additive migration same as
  sort_order. Comfort/fit/season for jewelry are force-cleared server-side
  in `_read_form_item()`, not just hidden in the form's JS — a hidden
  field still submits its last value, so the client-side toggle alone
  would've been a trap for a later edit.
- Hit the same `[hidden]` vs `.field { display:flex }` footgun this app's
  bitten before (closet filters, dropdown panels) — added the explicit
  `[hidden] { display:none }` overrides for `.field` and `.rating` up
  front this time instead of rediscovering it.
- 121 tests (+8). Verified in browser against a DB copy: added a real
  jewelry item through the actual add form (real upload, real rembg),
  confirmed condition-only + subtype saved correctly and it landed last
  on the closet grid.

## 2026-09-12 (even later) — swimsuit + belt
- Quick add: `swimsuit` as a plain clothing type. `belt` turned out to
  already exist (predates today's jewelry/shoes/accessory sort-after-
  clothes work) — asked Beck whether it should join that group now that
  it exists; he said yes, so it's in NON_CLOTHING_TYPES too. Neither
  existed in Beck's real closet.db yet, so no existing items reshuffled.
- 122 tests.

## 2026-09-12 (yet later) — touch-up: an actual full restore
- Beck's complaint: when rembg removes too much, the existing "Restore"
  brush only paints back whatever you manually brush over — tedious and
  not really "restore" when the cutout is badly mangled. He wants a
  button that fully brings back the original photo, then he erases the
  background himself by hand.
- Added a one-click "Restore original" button: replaces the whole canvas
  with the untouched raw photo (background and all) and drops you into
  Erase mode automatically. Kept the existing brush-mode "paint back a
  small patch" behavior too (still useful for a sleeve/hem-sized mistake)
  but renamed its button label to "Paint back" so two things both called
  "Restore" don't sit side by side in the same toolbar.
- Verified in the browser against a DB copy rather than trust it by
  reading: sampled a corner pixel before/after — transparent (the AI
  cutout) to the real background color — confirmed Undo reverses it, and
  both raw-dependent buttons disable correctly when there's no raw photo
  on file.
- 124 tests (+2).

## 2026-09-12 (last one, I think) — item status + more sources
- Two new sources: secondhand, idk. Quick.
- Bigger one: status tags (clean/dirty/loaned/lost/broken). Asked Beck
  whether "clothing items" auto-dirty on wear meant literally just
  clothing or everything including jewelry/shoes/accessories/belts —
  he confirmed clothing only, matching what he actually said.
- Kept status completely separate from the edit form on purpose:
  save_item() never lists status/status_note in its INSERT/UPDATE
  columns, so editing an item's name or color can never accidentally
  reset its status. It's its own route, its own quick-set pills on the
  item page, same spirit as the existing "Worn today" button.
- Auto-dirty hooks into the three places a wear_log row actually gets
  created (log_items_worn, log_outfit_worn, save_day_layout's newly-
  placed set) rather than one central place, since there isn't one —
  wrote a test specifically for the subtle case: resaving a board with
  the same items already on it should NOT re-dirty something you'd
  manually cleaned in the meantime, since it's not "newly placed".
- 141 tests (+17). Verified in the browser against a DB copy end to end:
  set an item to loaned with a note, watched it persist and the grid
  badge appear; "Worn today" dirtied a t-shirt but left jewelry clean.

## 2026-09-12 (actually last one) — stale closet-grid thumbnails
- Beck: touch-up edits showed on the item page but not the closet grid.
  Root cause was staring right at the docstring — `ensure_thumb()` really
  does regenerate the thumbnail file correctly on the server the moment
  the source is newer. The bug was the *browser*: `/thumbs/...` is served
  with `max_age=30 days`, and the URL for a given item's thumbnail never
  changes, so a browser that had already loaded the closet grid once just
  kept serving its own cached copy and never asked the server again —
  `/photos/...` (the item page) isn't cached that aggressively, which is
  exactly why the edit showed up there and nowhere else.
- Fix is the standard one: make the URL change when the content does.
  `thumb_url()` appends `?v=<mtime>`, registered once as a Jinja global so
  every template (closet grid, both trays, month grid, outfits list) and
  every Python call site (stats' three thumb lists, outfit-piece
  rendering) go through the same function instead of five separate
  `url_for('thumbs', ...)` call sites drifting out of sync.
- Verified against the *real* repo, not just a DB copy, since this bug is
  about a real file's mtime — bumped data/processed/001.png's mtime by an
  hour with `touch`, confirmed the rendered `?v=` changed, then restored
  the exact original mtime. No content or git changes either way.
- 145 tests (+4).

## 2026-09-12 (okay, actually last) — pulled the touch-up gray instructions
- Beck: "take out the gray instructions you added for touch up! remember, I
  don't like the gray instructions in general." Right — the Batch 10 work
  added a `.subhint` paragraph explaining Erase/Paint back/Restore original,
  which is exactly the pattern the standing no-instructions rule already
  covers. Should have skipped it or asked; didn't catch myself this time.
- Removed the paragraph + its now-unused CSS, restored the title's spacing.
  Updated the memory file with a concrete recurrence note instead of just
  trusting I'll remember next time.
- 113 tests. Verified in browser: click save -> landed on /calendar/2026/9.
