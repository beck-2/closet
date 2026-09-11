# TODO

## Batch 4 — calendar polish (requested 2026-09-11)  ✅ DONE
- [x] Month-grid day cells: loose-item thumbnails enlarged 30px → 46px; a
      logged outfit now renders as the same arranged mini-board used in
      outfit_builder/outfits_list/day-detail, not a flat row of pieces.
      Capped at 4 items / 2 outfit-boards per cell with a "+N" overflow badge.
      (Had to rename the day-info dict's "items" key to "loose_items" — it
      was colliding with dict.items() in Jinja's attribute lookup.)
- [x] Optional per-day comfort rating (1-3 dots, same pattern as item
      ratings) + free-text notes, new `day_log` table (worn_on PK), only
      shown on the day-detail page (`/calendar/day/<date>`) — nothing new
      in the month grid. A "clear" link unchecks an accidental rating.
      Saving both empty deletes the row instead of leaving clutter.
- [x] The day-detail page already rendered a logged outfit as a mini-board
      (built in the earlier calendar batch) — confirmed, no change needed.
- [x] tests/test_calendar.py (+13). Verified in browser against a copy of
      the real DB: mini-board renders 3 arranged pieces, thumbs visibly
      bigger, rating+notes save/clear round-trip.

## Batch 3 — analytics dashboard (requested 2026-09-10)  ✅ DONE
- [x] New "Stats" nav pill + `/stats` page. Three sections.
- [x] Wardrobe: colour donut (hand-rolled SVG), item-type bars, source bars.
- [x] Wear: closet-in-rotation (worn N of 74 in last 30/90 days), most-worn list.
- [x] Money (collapsed `<details>`, choice remembered in localStorage): total
      spent, blended avg cost-per-wear, best value, closet regrets.
- [x] Per-item cost-per-wear stays on the item page; added "last worn Sep 8".
- [x] No new deps — SVG + CSS charts.
- [x] tests/test_stats.py (9). Verified in the browser.
- Beck's picks: type + source breakdowns; utilization %; best value + regrets;
  money section starts collapsed. Skipped: season coverage, worn-once club,
  activity-over-time, spend-by-source/type (for now).

## Batch 2 (requested 2026-09-09)

### 5. Drag to rearrange the closet grid; persist the order  ✅ DONE
- [x] `items.sort_order INTEGER` + idempotent ALTER migration. `load_items()`
      orders by `sort_order IS NULL, sort_order, id` — placed items first,
      never-dragged ones after (so new items land at the end).
- [x] Pointer-based drag on the grid (6px threshold to tell drag from click);
      clicking a card still navigates. `POST /closet/order` persists.
- [x] Drag disabled while a filter/search is active (order is only meaningful
      in the natural view); the shared filter script keeps `originalOrder` in
      sync after a drag so search-clear restores the *new* order.
- [x] tests/test_closet_order.py (7). Verified drag + persist + click-still-
      navigates + disabled-while-filtering in the browser.

### 6. Fix the touch-up "restore to original" bug  ✅ DONE
- [x] Root cause confirmed: the "original" backup was captured lazily from
      whatever was on disk when the touch-up page first opened, so for
      rembg-mangled items it was already the broken cutout — "Reset" restored
      the broken version. Also the reset was a flaky async server fetch.
- [x] "Reset" now restores a synchronous snapshot taken at page load —
      reliable, always reverts to the opened state.
- [x] New **Restore brush**: paints the garment back from the original photo
      (`/item/<id>/photo/<i>/raw` — EXIF-rotated, resized to the cutout's
      dimensions so it aligns). Disabled when no raw is on file.
- [x] Damaged items are the 3 unnamed ones (028, 039, 040) — Beck wants to
      re-fix them himself with the new tool, so no auto-recovery.
- [x] Removed the now-dead `data/originals/` backup machinery entirely.
- [x] tests/test_touchup.py (5). Verified the restore brush + reset on item
      028 in the browser (painted a sleeve back from the raw photo).

### 7. Calendar tab — what was worn each day  ✅ DONE
- [x] "Calendar" pill in the navbar.
- [x] `wear_log` table: one row per piece worn (outfit_id set when the piece
      came from logging a whole outfit, NULL when it's a loose item).
- [x] Month grid (`/calendar`, `/calendar/<y>/<m>`) — days with wears show
      thumbnails; today ringed; future days greyed and not clickable.
- [x] Day detail (`/calendar/day/<date>`) — what's logged (with ✕ remove),
      plus a searchable tile picker + outfit dropdown to add. Any past day.
- [x] "Worn today" now logs into the calendar for today; every item's
      wear_count / cost-per-wear derives from wear_log (the stored
      items.wear_count column is retired — kept in the schema, unread).
- [x] Beck's answers: log both items AND outfits; backfill any past day;
      keep "Worn today" wired to it.
- [x] tests/test_calendar.py (12). Verified the whole flow in the browser:
      log items + an outfit on a past day, see them on the month grid, "Worn
      today" → today's entry, remove, wear count follows.

---

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
