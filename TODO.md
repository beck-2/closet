# TODO — feature batch (requested 2026-09-09)

## 1. Flexible "date acquired" — year, or month + year  ✅ DONE
- [x] Storage: `date_acquired TEXT` unchanged; now accepts `"YYYY"` and `"YYYY-MM"`.
- [x] Add/Edit form: year `<select>` + optional month `<select>`.
- [x] Item view: `acquired_display` filter → "March 2025" / "2025" / "—".
- [x] Tests in tests/test_date_acquired.py (7). Verified in browser.

## 2. Gold stars (max 5 awarded pieces, pinned to top of closet)
- [ ] Storage: per-item `starred_at TEXT` (null = not starred; timestamp gives
      award order). Migration-safe.
- [ ] Cap = 5. Awarding a 6th **bumps the oldest** star automatically.
- [ ] Toggle control on the item view page.
- [ ] Closet page: a "gold stars" section pinned above the normal grid.
- [ ] Tests.

## 3. Richer closet filtering + name search
- [ ] Dropdowns: item_type, color, season, source.
- [ ] Text search: name, and vibes (substring).
- [ ] Filters combine (AND). Client-side over the rendered grid.
- [ ] Gold-star section stays pinned; filtering applies within it too.
- [ ] Tests.

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
