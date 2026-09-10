# TODO — feature batch (requested 2026-09-09)

## 1. Flexible "date acquired" — year, or month + year  ✅ DONE
- [x] Storage: `date_acquired TEXT` unchanged; now accepts `"YYYY"` and `"YYYY-MM"`.
- [x] Add/Edit form: year `<select>` + optional month `<select>`.
- [x] Item view: `acquired_display` filter → "March 2025" / "2025" / "—".
- [x] Tests in tests/test_date_acquired.py (7). Verified in browser.

## 2. Gold stars  ❌ REMOVED (2026-09-09, Beck's call)
- Built, shipped (ece8f76), then Beck decided he didn't want it. Fully
  removed in a later commit — star column dropped from the schema, all
  routes/UI/tests gone. Beck's existing closet.db keeps an unused
  `starred_at` column (harmless; not worth a destructive migration).

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

### 3d. Filter bug + search-as-ranking (2026-09-09)  ✅ DONE
- [x] BUG: checkboxes set `card.hidden` but `.pg-closet .card { display:block }`
      beat the UA `[hidden]{display:none}` — nothing ever visually hid.
      Fixed with `.pg-closet .card[hidden] { display:none }` (same class-vs-
      [hidden] trap as the dropdown panel). Verified with real clicks +
      `getComputedStyle`, not just the attribute.
- [x] Name/vibes search now RANKS instead of filtering: matches float to the
      top by relevance (exact > prefix > word-prefix > substring), nothing
      is hidden, and clearing the box restores the original id order.
      Checkboxes still hide. Verified all of it in the browser.

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
