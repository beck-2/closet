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
- [x] Dropdowns: type, color, season, source (options = values present).
- [x] Text search: name + vibes (substring, live).
- [x] Filters AND together, client-side over every rendered `.card`.
- [x] Gold section hides itself when nothing starred matches; "nothing
      matches" message; a "clear" button appears when any filter is active.
- [x] Server side: `?type=` query filter removed (now client-side).
- [x] Tests in tests/test_filters.py (4) + updated test_app. Verified in
      browser (type/name/combined/clear/no-match all work).

## 4. Outfit board + outfits list
- [ ] Verify the already-built board behaviour works: drag from closet,
      resize, right-click front/back, drag auto-raises to top.
- [ ] Outfits-list thumbnail: render the actual arranged board (scaled),
      not a plain row of pieces. (`_outfit_render_pieces` already computes
      the percentages; the template just doesn't use them — also fixes the
      current empty-boxes bug.)
- [ ] "edit" button next to "+ new outfit" → an edit-mode toggle; in edit
      mode each outfit card shows edit + delete.
- [ ] Tests.

## Found along the way (not requested — for later)
- Editing an item drops any color not in the checkbox suggestions: the
  "other colors" text box never pre-fills the item's current free-form
  colors, so they're lost on the next save. (Spotted: item 001's "grey".)

## Decisions (from Beck, 2026-09-09)
- Star cap: bump the oldest.
- Filter dropdowns: item_type, color, season, source. Text search: name + vibes.
- Outfit list edit: edit-mode toggle.
- date_acquired year dropdown: 2010 → current year.
