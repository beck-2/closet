# TODO — feature batch (requested 2026-09-09)

## 1. Flexible "date acquired" — year, or month + year  ✅ DONE
- [x] Storage: `date_acquired TEXT` unchanged; now accepts `"YYYY"` and `"YYYY-MM"`.
- [x] Add/Edit form: year `<select>` + optional month `<select>`.
- [x] Item view: `acquired_display` filter → "March 2025" / "2025" / "—".
- [x] Tests in tests/test_date_acquired.py (7). Verified in browser.

## 2. Gold stars (max 5 awarded pieces, pinned to top of closet)  ✅ DONE
- [x] Storage: `items.starred_at TEXT` + `_run_column_migrations` (ALTER on
      existing DBs, idempotent). Verified on a copy of the real 74-item DB.
- [x] `db.set_star` enforces cap 5, bumps the oldest on a 6th award.
- [x] `POST /item/<id>/star` toggle on the item view page.
- [x] Closet: "★ gold stars" section above the grid, starred cards not
      duplicated below. Gold border + corner star badge.
- [x] Tests in tests/test_gold_stars.py (8). Verified in browser.

## 3. Richer closet filtering + name search  ✅ DONE
- [x] Text search: name + vibes (substring, live).
- [x] Filters AND together, client-side over every rendered `.card`.
- [x] Gold section hides itself when nothing starred matches; "nothing
      matches" message; a "clear" button appears when any filter is active.
- [x] Server side: `?type=` query filter removed (now client-side).
- [x] Tests + browser verification.

### 3b/3c. Filters: multi-select, then collapse into dropdowns (2026-09-09)  ✅ DONE
- [x] Type/color/season/source are multi-select and apply instantly.
- [x] Multiple selections in one facet = OR ("from sat OR bauer");
      facets still AND together.
- [x] 3c: the ~40 always-visible chips were too much — each facet is now a
      collapsed dropdown button ("Type ▾") that opens a checkbox panel.
      One panel open at a time; outside-click / Esc closes; a count badge
      ("Source 2") shows on the button when selections are active.
- [x] Card data-attrs pipe-joined (`data-color="blue|black"`) so values
      with spaces ("from sat") match cleanly.
- [x] Empty facet → no dropdown. "clear all" resets everything.
- [x] tests/test_filters.py; verified open/close/OR/AND/badge/clear in browser.

## 4. Outfit board + outfits list  ✅ DONE
- [x] Verified in browser — drag-from-closet, corner-handle resize,
      right-click front/back/remove, drag-auto-to-top all already worked.
      No code change needed there.
- [x] Outfits-list thumbnail: real arranged mini-board (`.miniboard` with
      absolutely-positioned `.minipiece` at the saved %s + rotation).
      Fixes the old empty-boxes bug. Uses `/thumbs/` for the piece images
      (new `thumb_src` on `_outfit_render_pieces`).
- [x] Whole outfit card is a link straight into the builder (2026-09-09
      follow-up). "manage" toggle next to "+ new outfit" reveals a 🗑 delete
      per card (delete confirms).
- [x] Tests in tests/test_outfits.py (7). Verified end-to-end: built an
      outfit in the browser, saved, saw the arrangement in the list,
      clicked it back open.

## Found along the way (not requested — for later)
- Editing an item drops any color not in the checkbox suggestions: the
  "other colors" text box never pre-fills the item's current free-form
  colors, so they're lost on the next save. (Spotted: item 001's "grey".)

## Decisions (from Beck, 2026-09-09)
- Star cap: bump the oldest.
- Filter dropdowns: item_type, color, season, source. Text search: name + vibes.
- Outfit list edit: edit-mode toggle.
- date_acquired year dropdown: 2010 → current year.
