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
- Next: step 3, security (CSRF + upload validation).
