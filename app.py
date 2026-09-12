#!/usr/bin/env python3
"""
beck's closet — a tiny local web app, backed by a SQLite database
(data/closet.db).

Run it with:
    python3 app.py

Then open http://127.0.0.1:8000 in your browser.
"""
from __future__ import annotations

import calendar
import datetime
import logging
import os
from pathlib import Path
from urllib.parse import urlparse

from flask import (
    Flask,
    Response,
    abort,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)

import db
from pipeline.metadata_schema import (
    ACQUIRED_MIN_YEAR,
    COLOR_SUGGESTIONS,
    ITEM_TYPES,
    JEWELRY_SUBTYPES,
    RATING_FIELDS,
    RATING_MAX,
    RATING_MIN,
    SEASON_SUGGESTIONS,
    SOURCES,
    STATUSES,
)

# Month options for the "date acquired" picker: [("1", "January"), ...].
ACQUIRED_MONTHS = [(str(m), calendar.month_name[m]) for m in range(1, 13)]


def acquired_years() -> list[int]:
    """Year options for the picker, newest first, ACQUIRED_MIN_YEAR..this year."""
    return list(range(datetime.date.today().year, ACQUIRED_MIN_YEAR - 1, -1))

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
THUMBS_DIR = DATA_DIR / "thumbs"

# Grid views (the closet, the outfit-builder tray) only ever show a photo a
# couple hundred px wide, so they pull a cached downscaled copy instead of
# the full ~1MB 1024px cutout. Thumbs are regenerated whenever the source
# cutout is newer than the cached thumb (e.g. after a touch-up).
THUMB_LONG_EDGE = 400

# The outfit board is a fixed-size canvas (see .pg-outfits .board in
# style.css) — not responsive — specifically so that every x/y/w placement
# saved for an outfit is a raw pixel value against this exact, known box.
# That's what lets the board's arrangement be reconstructed faithfully
# both in the little outfits-list thumbnail and when reopening it to edit.
OUTFIT_BOARD_W = 600
OUTFIT_BOARD_H = 620

# Largest upload we'll accept, in bytes. A phone photo is a few MB; this is a
# generous ceiling that still stops a runaway upload from filling memory/disk.
MAX_UPLOAD_BYTES = 25 * 1024 * 1024

app = Flask(__name__)
app.config["DB_PATH"] = os.environ.get("CLOSET_DB_PATH", str(db.DB_PATH))
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES
app.teardown_appcontext(db.close_db)

with app.app_context():
    db.init_db()

# A handful of named colors get an actual swatch dot; anything else just
# shows as text without one.
COLOR_HEX = {
    "black": "#2b2140", "white": "#ffffff", "gray": "#9a94a6", "brown": "#7b5a3e",
    "beige": "#e4d3ae", "cream": "#f7efe0", "red": "#e0393e", "orange": "#f2884b",
    "yellow": "#ffd447", "green": "#5c9a63", "blue": "#5ec8e8", "purple": "#7c3aa0",
    "pink": "#ff6fa5", "multicolor": "conic-gradient(#e0393e,#ffd447,#5c9a63,#5ec8e8,#7c3aa0,#ff6fa5,#e0393e)",
}


# ------------------------------------------------------------- filesystem --
# (photo storage stays on disk regardless of what holds the metadata)

def next_item_id() -> str:
    existing = [int(i) for i in db.existing_item_ids() if i.isdigit()]
    return f"{(max(existing) + 1) if existing else 1:03d}"


def next_photo_stub(item_id: str) -> str:
    """First extra photo for an item is '<id>_2', then '<id>_3', etc. — picked
    by scanning disk so it never collides with a file left over from an
    earlier add/delete."""
    n = 2
    while True:
        stub = f"{item_id}_{n}"
        if not list(PROCESSED_DIR.glob(f"{stub}.*")) and not list(RAW_DIR.glob(f"{stub}.*")):
            return stub
        n += 1


def process_upload(file_storage, stub: str, session) -> tuple[str, str]:
    """Save an uploaded photo as data/raw/<stub><ext> and run it through the
    background-removal/resize pipeline into data/processed/<stub>.png.
    Returns (raw_rel_path, processed_rel_path); raises ValueError on failure."""
    from pipeline.config import OUTPUT_EXTENSION
    from pipeline.process_images import process_one

    raw_ext = Path(file_storage.filename).suffix.lower() or ".jpg"
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    raw_path = RAW_DIR / f"{stub}{raw_ext}"
    file_storage.save(raw_path)

    result = process_one(raw_path, RAW_DIR, PROCESSED_DIR, session, overwrite=True)
    if result.status == "error":
        raw_path.unlink(missing_ok=True)
        raise ValueError(result.detail)
    processed_rel = f"data/processed/{stub}{OUTPUT_EXTENSION}"
    return f"data/raw/{stub}{raw_ext}", processed_rel


def cost_per_wear(item: dict):
    price, worn = item.get("price"), item.get("wear_count") or 0
    if price is None or not worn:
        return None
    return round(price / worn, 2)


def avg_rating(item: dict):
    vals = [item.get(f) for f in RATING_FIELDS if item.get(f)]
    return round(sum(vals) / len(vals)) if vals else 0


def _pretty_day(iso: str | None) -> str | None:
    """'2026-09-09' -> 'Sep 9, 2026'."""
    if not iso:
        return None
    d = datetime.date.fromisoformat(iso)
    return f"{d.strftime('%b')} {d.day}, {d.year}"


@app.context_processor
def inject_globals():
    total = db.count_items()
    return {"total_str": f"{total:03d}" if total < 1000 else str(total)}


# --------------------------------------------------------- request guard --
# This app has no login and binds to localhost, but a web page open in the
# same browser can still fire POSTs at http://127.0.0.1:8000 (classic CSRF —
# bump wear counts, delete outfits, etc.). Browsers attach an Origin (or at
# least a Referer) to any state-changing request, so we reject a write whose
# Origin/Referer names a different host. A request carrying neither header
# (curl, the test client, local scripts) is let through — that's not a
# browser and isn't the threat this guards against.

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def _same_host(url: str | None) -> bool:
    if not url:
        return False
    return urlparse(url).netloc == request.host


@app.before_request
def block_cross_site_writes():
    if request.method in _SAFE_METHODS:
        return
    origin = request.headers.get("Origin")
    if origin is not None:
        if not _same_host(origin):
            abort(403)
        return
    referer = request.headers.get("Referer")
    if referer is not None and not _same_host(referer):
        abort(403)


# ------------------------------------------------------------------ views --

def _distinct_values(items: list[dict], key: str) -> list[str]:
    """Every value present for `key` across the closet, sorted. Handles both
    scalar fields (item_type, source) and list fields (color, season)."""
    vals: set[str] = set()
    for item in items:
        v = item.get(key)
        if isinstance(v, list):
            vals.update(v)
        elif v:
            vals.add(v)
    return sorted(vals)


@app.route("/")
def closet():
    items = db.load_items()  # already in the user's chosen order (see db._ITEM_ORDER)
    all_items = list(items.values())
    cards = [{**it, "rating": avg_rating(it)} for it in all_items]

    # Options for the filter dropdowns — filtering itself is done client-side.
    filter_options = {
        "type": _distinct_values(all_items, "item_type"),
        "color": _distinct_values(all_items, "color"),
        "season": _distinct_values(all_items, "season"),
        "source": _distinct_values(all_items, "source"),
    }

    return render_template(
        "closet.html",
        active="closet",
        cards=cards,
        filter_options=filter_options,
    )


@app.route("/item/<item_id>")
def item_view(item_id):
    item = db.get_item(item_id)
    if item is None:
        abort(404)
    return render_template(
        "item_view.html",
        active="closet",
        item=item,
        item_id=item_id,
        color_hex=COLOR_HEX,
        cost_per_wear=cost_per_wear(item),
        last_worn=_pretty_day(db.last_worn(item_id)),
        statuses=STATUSES,
    )


@app.route("/closet/order", methods=["POST"])
def save_closet_order():
    payload = request.get_json(silent=True) or {}
    order = payload.get("order")
    if not isinstance(order, list) or not all(isinstance(i, str) for i in order):
        return jsonify({"ok": False, "error": "expected {order: [id, …]}"}), 400
    db.set_closet_order(order)
    return jsonify({"ok": True})


@app.route("/item/<item_id>/worn", methods=["POST"])
def mark_worn(item_id):
    if db.get_item(item_id) is None:
        abort(404)
    db.log_items_worn(datetime.date.today().isoformat(), [item_id])
    return redirect(url_for("item_view", item_id=item_id))


@app.route("/item/<item_id>/status", methods=["POST"])
def set_item_status(item_id):
    if db.get_item(item_id) is None:
        abort(404)
    status = request.form.get("status") or "clean"
    if status not in STATUSES:
        abort(400)
    note = (request.form.get("note") or "").strip()
    db.set_item_status(item_id, status, note if status == "loaned" else None)
    return redirect(url_for("item_view", item_id=item_id))


# --------------------------------------------------------------- calendar --

# A month-grid day cell shows at most this many "tiles" (each tile is one
# board — either a saved outfit or the day's ad-hoc arrangement) so every
# cell stays a uniform, compact size; anything past this is a "+N" badge.
DAY_CELL_MAX_TILES = 1


def _day_board_pieces(worn_on: str, items: dict, loose_items: list[dict]) -> list[dict]:
    """The day's ad-hoc board: pieces already given a saved position, plus
    any loose item logged for the day that doesn't have one yet — those get
    auto-placed the same staggered way a freshly-dragged-in piece would, so
    nothing you've logged is ever missing from the board."""
    layout = db.get_day_layout(worn_on)
    positioned_ids = {p["id"] for p in layout}
    start = len(layout)
    default_w = 220
    unplaced = [it for it in loose_items if it["id"] not in positioned_ids]
    for i, it in enumerate(unplaced):
        idx = start + i
        layout.append({
            "id": it["id"],
            "x": 60 + (idx * 40) % (OUTFIT_BOARD_W - default_w - 40),
            "y": 40 + (idx * 55) % (OUTFIT_BOARD_H - 160),
            "w": default_w,
            "rot": 0,
        })
    return _outfit_render_pieces({"layout": layout}, items)


def _day_tiles(info: dict, items: dict, outfits: dict, worn_on: str) -> dict:
    """What to show in one month-grid day cell — each saved outfit logged
    that day, plus the day's ad-hoc board if it has anything on it. Every
    tile is the same board shape, capped at DAY_CELL_MAX_TILES with a
    "+N" badge for the rest."""
    tiles = []
    for oid in info["outfit_ids"]:
        outfit = outfits.get(oid)
        if outfit is None:
            continue
        pieces = _outfit_render_pieces(outfit, items)
        if pieces:
            tiles.append({"name": outfit["name"], "pieces": pieces})
    loose = [items[iid] for iid in info["item_ids"] if iid in items]
    if loose:
        pieces = _day_board_pieces(worn_on, items, loose)
        if pieces:
            tiles.append({"name": None, "pieces": pieces})
    return {"tiles": tiles[:DAY_CELL_MAX_TILES], "more": max(0, len(tiles) - DAY_CELL_MAX_TILES)}


@app.route("/calendar")
@app.route("/calendar/<int:year>/<int:month>")
def calendar_view(year: int | None = None, month: int | None = None):
    today = datetime.date.today()
    if year is None:
        year, month = today.year, today.month
    if not (1 <= month <= 12) or not (1900 <= year <= 2200):
        abort(404)

    items = db.load_items()
    outfits = {o["id"]: o for o in db.load_outfits()}
    summary = db.wear_summary_for_month(year, month)
    days = {d: _day_tiles(info, items, outfits, d) for d, info in summary.items()}

    weeks = calendar.Calendar(firstweekday=6).monthdatescalendar(year, month)
    first = datetime.date(year, month, 1)
    prev_d = first - datetime.timedelta(days=1)
    next_d = (first + datetime.timedelta(days=32)).replace(day=1)
    return render_template(
        "calendar.html",
        active="calendar",
        year=year,
        month=month,
        month_name=calendar.month_name[month],
        weeks=weeks,
        days=days,
        today=today,
        prev=(prev_d.year, prev_d.month),
        next=(next_d.year, next_d.month),
    )


def _parse_day(date: str) -> datetime.date:
    try:
        return datetime.date.fromisoformat(date)
    except ValueError:
        abort(404)


@app.route("/calendar/day/<date>")
def calendar_day(date):
    d = _parse_day(date)
    if d > datetime.date.today():
        abort(404)
    items = db.load_items()
    worn = db.wears_on(date)
    for outfit in worn["outfits"]:
        outfit["pieces"] = _outfit_render_pieces(outfit, items)
    return render_template(
        "calendar_day.html",
        active="calendar",
        date=date,
        pretty_date=d.strftime("%A, %B ") + str(d.day) + d.strftime(", %Y"),
        worn_outfits=worn["outfits"],
        board_pieces=_day_board_pieces(date, items, worn["items"]),
        tray=[{"id": i, **items[i]} for i in items],
        outfits=db.load_outfits(),
        day_log=db.get_day_log(date),
        rating_min=RATING_MIN,
        rating_max=RATING_MAX,
        calendar_url=url_for("calendar_view", year=d.year, month=d.month),
    )


@app.route("/calendar/day/<date>", methods=["POST"])
def calendar_day_log(date):
    d = _parse_day(date)
    if d > datetime.date.today():
        abort(400, description="can't log a day that hasn't happened yet")
    outfit_id = (request.form.get("outfit_id") or "").strip()
    if outfit_id:
        db.log_outfit_worn(date, outfit_id)
    return redirect(url_for("calendar_day", date=date))


@app.route("/calendar/day/<date>/board", methods=["POST"])
def calendar_day_board(date):
    d = _parse_day(date)
    if d > datetime.date.today():
        return jsonify({"ok": False, "error": "can't log a day that hasn't happened yet"}), 400
    payload = request.get_json(force=True, silent=True) or {}
    placements = _clean_placements(payload.get("items") or [])
    if placements is None:
        return jsonify({"ok": False, "error": "malformed item placement"}), 400
    db.save_day_layout(date, placements)
    return jsonify({"ok": True})


@app.route("/calendar/day/<date>/note", methods=["POST"])
def calendar_day_note(date):
    _parse_day(date)
    raw = (request.form.get("comfort") or "").strip()
    comfort = int(raw) if raw.isdigit() and RATING_MIN <= int(raw) <= RATING_MAX else None
    notes = (request.form.get("notes") or "").strip()
    db.save_day_log(date, comfort, notes)
    return redirect(url_for("calendar_day", date=date))


@app.route("/calendar/day/<date>/remove", methods=["POST"])
def calendar_day_remove(date):
    """Un-log a saved outfit from this day. Loose ad-hoc pieces are removed
    by editing the day's board instead (see calendar_day_board)."""
    _parse_day(date)
    outfit_id = request.form.get("id")
    if outfit_id:
        db.unlog_outfit(date, outfit_id)
    return redirect(url_for("calendar_day", date=date))


# ------------------------------------------------------------------ stats --

def _counter(pairs: list, labeller=lambda v: v) -> list[dict]:
    """[(label, count), …] biggest first, from an iterable of raw values."""
    tally: dict = {}
    for value in pairs:
        key = labeller(value) if value else labeller(None)
        tally[key] = tally.get(key, 0) + 1
    return [
        {"label": k, "count": n}
        for k, n in sorted(tally.items(), key=lambda kv: (-kv[1], str(kv[0])))
    ]


def _donut(segments: list[dict], radius: float = 60, stroke: float = 26) -> dict:
    """Turn [{label,count,color}, …] into ready-to-draw SVG donut segments."""
    total = sum(s["count"] for s in segments) or 1
    circ = 2 * 3.141592653589793 * radius
    offset = 0.0
    drawn = []
    for s in segments:
        frac = s["count"] / total
        drawn.append({
            **s,
            "pct": round(frac * 100),
            "dash": round(frac * circ, 2),
            "gap": round(circ - frac * circ, 2),
            "offset": round(-offset, 2),
        })
        offset += frac * circ
    return {"radius": radius, "stroke": stroke, "circ": round(circ, 2), "segments": drawn}


@app.route("/stats")
def stats_view():
    items = list(db.load_items().values())
    n = len(items)
    counts = db.wear_counts()  # {id: days worn}
    for it in items:
        it["wear_count"] = counts.get(it["id"], 0)

    def thumb(it):
        return thumb_url(it["images"][0]) if it.get("images") else None

    # --- wardrobe ---
    colors = _counter([c for it in items for c in (it.get("color") or [])])
    for c in colors:
        c["color"] = COLOR_HEX.get(c["label"], "#d8cdb0")
    types = _counter([it.get("item_type") for it in items], lambda v: v or "unlabeled")
    sources = _counter([it.get("source") for it in items], lambda v: v or "unknown")

    # --- wear ---
    worn_items = sorted(
        (it for it in items if it["wear_count"]), key=lambda it: -it["wear_count"]
    )
    most_worn = [
        {"id": it["id"], "name": it.get("name") or it.get("item_type") or "item",
         "count": it["wear_count"], "thumb": thumb(it)}
        for it in worn_items[:25]
    ]
    today = datetime.date.today()
    util = {
        window: {
            "worn": len(db.items_worn_since((today - datetime.timedelta(days=window)).isoformat())),
            "total": n,
        }
        for window in (30, 90)
    }

    # --- money (rendered inside a collapsed section) ---
    priced = [it for it in items if it.get("price") is not None]
    total_spent = round(sum(it["price"] for it in priced), 2)
    # Average includes free pieces (a $0 gift you wear a lot really does
    # drag your average down)...
    priced_and_worn = [it for it in priced if it["wear_count"]]
    total_wears = sum(it["wear_count"] for it in priced_and_worn)
    avg_cpw = (
        round(sum(it["price"] for it in priced_and_worn) / total_wears, 2)
        if total_wears
        else None
    )
    # ...but "best value" only ranks pieces that actually cost something.
    best_value = sorted(
        (it for it in priced_and_worn if it["price"]),
        key=lambda it: it["price"] / it["wear_count"],
    )[:5]
    best_value = [
        {"id": it["id"], "name": it.get("name") or it.get("item_type") or "item",
         "cpw": round(it["price"] / it["wear_count"], 2), "count": it["wear_count"],
         "thumb": thumb(it)}
        for it in best_value
    ]
    regrets = sorted(
        (it for it in priced if not it["wear_count"] and it["price"]),
        key=lambda it: -it["price"],
    )[:5]
    regrets = [
        {"id": it["id"], "name": it.get("name") or it.get("item_type") or "item",
         "price": it["price"], "thumb": thumb(it)}
        for it in regrets
    ]

    return render_template(
        "stats.html",
        active="stats",
        colors=colors,
        color_donut=_donut(colors),
        types=types,
        sources=sources,
        most_worn=most_worn,
        util=util,
        money={
            "total_spent": total_spent,
            "priced_count": len(priced),
            "avg_cpw": avg_cpw,
            "best_value": best_value,
            "regrets": regrets,
        },
    )


def _read_form_item(form) -> dict:
    def multi(name):
        vals = form.getlist(name)
        extra = (form.get(f"{name}_other") or "").strip()
        if extra:
            vals += [c.strip() for c in extra.split(",") if c.strip()]
        return vals

    def rating(name):
        raw = form.get(name)
        return int(raw) if raw else None

    def num(name):
        raw = (form.get(name) or "").strip()
        try:
            return float(raw) if raw else None
        except ValueError:
            return None

    vibes_raw = (form.get("vibes") or "").strip()
    vibes = [v.strip() for v in vibes_raw.split(",") if v.strip()]

    item_type = form.get("item_type") or None
    # Jewelry only tracks a condition rating (no comfort/fit) and has no
    # seasons — enforced here too, not just hidden client-side, since a
    # field that's merely hidden still submits whatever value it last had.
    is_jewelry = item_type == "jewelry"

    return {
        "name": (form.get("name") or "").strip() or None,
        "item_type": item_type,
        "jewelry_subtype": (form.get("jewelry_subtype") or None) if is_jewelry else None,
        "color": multi("color"),
        "comfort": None if is_jewelry else rating("comfort"),
        "fit": None if is_jewelry else rating("fit"),
        "condition": rating("condition"),
        "vibes": vibes,
        "source": form.get("source") or None,
        "price": num("price"),
        "date_acquired": _form_date_acquired(form),
        "season": [] if is_jewelry else multi("season"),
        "notes": (form.get("notes") or "").strip(),
    }


def _form_date_acquired(form) -> str | None:
    """Combine the year + optional month dropdowns into "YYYY" or "YYYY-MM".
    A month with no year is meaningless, so it's dropped."""
    year = (form.get("date_acquired_year") or "").strip()
    month = (form.get("date_acquired_month") or "").strip()
    if not year:
        return None
    if month:
        return f"{year}-{int(month):02d}"
    return year


@app.template_filter("acquired_display")
def acquired_display(value: str | None) -> str:
    """"2025-03" -> "March 2025"; "2025" -> "2025"; empty -> em dash."""
    if not value:
        return "—"
    parts = value.split("-")
    if len(parts) == 2:
        return f"{calendar.month_name[int(parts[1])]} {parts[0]}"
    return parts[0]


def _edit_form_kwargs(item_id, item, error=None):
    return dict(
        active="closet",
        mode="edit",
        item_id=item_id,
        item=item,
        item_types=ITEM_TYPES,
        jewelry_subtypes=JEWELRY_SUBTYPES,
        color_suggestions=COLOR_SUGGESTIONS,
        season_suggestions=SEASON_SUGGESTIONS,
        sources=SOURCES,
        rating_min=RATING_MIN,
        rating_max=RATING_MAX,
        acquire_years=acquired_years(),
        acquire_months=ACQUIRED_MONTHS,
        error=error,
    )


@app.route("/item/<item_id>/edit", methods=["GET", "POST"])
def edit_item(item_id):
    item = db.get_item(item_id)
    if item is None:
        abort(404)

    if request.method == "POST":
        existing_images = item.get("images") or []
        existing_raw = item.get("raw_images") or []
        while len(existing_raw) < len(existing_images):
            existing_raw.append(None)

        to_delete = set(request.form.getlist("delete_image"))
        kept_images, kept_raw, removed, removed_raw = [], [], [], []
        for img, raw in zip(existing_images, existing_raw):
            if img in to_delete:
                removed.append(img)
                if raw:
                    removed_raw.append(raw)
            else:
                kept_images.append(img)
                kept_raw.append(raw)

        new_files = [f for f in request.files.getlist("new_photos") if f and f.filename]

        if not kept_images and not new_files:
            return render_template(
                "item_form.html",
                **_edit_form_kwargs(
                    item_id, item,
                    error="An item needs at least one photo — add a new one before removing the last.",
                ),
            ), 400

        new_processed, new_raw = [], []
        if new_files:
            from pipeline.process_images import get_session

            session = get_session()
            try:
                for f in new_files:
                    stub = next_photo_stub(item_id)
                    raw_rel, processed_rel = process_upload(f, stub, session)
                    new_raw.append(raw_rel)
                    new_processed.append(processed_rel)
            except ValueError as exc:
                for rel in new_processed:
                    (BASE_DIR / rel).unlink(missing_ok=True)
                return render_template(
                    "item_form.html",
                    **_edit_form_kwargs(item_id, item, error=f"Couldn't process a new photo: {exc}"),
                ), 400

        # Only remove files once we know the edit as a whole is going through.
        for rel in removed + removed_raw:
            (BASE_DIR / rel).unlink(missing_ok=True)
        for rel in removed:
            (THUMBS_DIR / Path(rel).name).unlink(missing_ok=True)

        updates = _read_form_item(request.form)
        updates["wear_count"] = item.get("wear_count") or 0
        updates["images"] = kept_images + new_processed
        updates["raw_images"] = kept_raw + new_raw
        db.save_item(item_id, updates)
        return redirect(url_for("item_view", item_id=item_id))

    return render_template("item_form.html", **_edit_form_kwargs(item_id, item))


@app.route("/item/<item_id>/photo/<int:index>/touchup", methods=["GET"])
def touchup_photo(item_id, index):
    item = db.get_item(item_id)
    if item is None:
        abort(404)
    images = item.get("images") or []
    if index < 0 or index >= len(images):
        abort(404)
    processed_rel = images[index]
    raws = item.get("raw_images") or []
    has_raw = index < len(raws) and bool(raws[index]) and (BASE_DIR / raws[index]).is_file()
    return render_template(
        "touchup.html",
        active="closet",
        item_id=item_id,
        index=index,
        processed_filename=processed_rel.split("/")[-1],
        raw_url=url_for("photo_raw", item_id=item_id, index=index) if has_raw else None,
    )


@app.route("/item/<item_id>/photo/<int:index>/raw")
def photo_raw(item_id, index):
    """The original uploaded photo (EXIF-rotated, scaled to match the processed
    cutout) — the touch-up tool's 'restore' brush paints from this to bring
    back anything the automatic cutout wrongly removed."""
    import io

    from PIL import Image, ImageOps

    item = db.get_item(item_id)
    if item is None:
        abort(404)
    images = item.get("images") or []
    raws = item.get("raw_images") or []
    if index < 0 or index >= len(images):
        abort(404)
    raw_rel = raws[index] if index < len(raws) else None
    if not raw_rel or not (BASE_DIR / raw_rel).is_file():
        abort(404)

    with Image.open(BASE_DIR / raw_rel) as raw, Image.open(BASE_DIR / images[index]) as proc:
        oriented = ImageOps.exif_transpose(raw).convert("RGB").resize(proc.size, Image.LANCZOS)
        buf = io.BytesIO()
        oriented.save(buf, format="JPEG", quality=88)
    return Response(buf.getvalue(), mimetype="image/jpeg", headers={"Cache-Control": "no-store"})


@app.route("/item/<item_id>/photo/<int:index>/touchup", methods=["POST"])
def save_touchup(item_id, index):
    item = db.get_item(item_id)
    if item is None:
        abort(404)
    images = item.get("images") or []
    if index < 0 or index >= len(images):
        abort(404)

    upload = request.files.get("image")
    if not upload or not upload.filename:
        abort(400, description="No touched-up image was sent.")

    import io

    from PIL import Image

    data = upload.read()
    try:
        with Image.open(io.BytesIO(data)) as check:
            check.verify()
        edited = Image.open(io.BytesIO(data)).convert("RGBA")
    except Exception:
        abort(400, description="That didn't look like a valid image.")

    target_path = BASE_DIR / images[index]
    edited.save(target_path, format="PNG")
    return jsonify({"ok": True})


def _add_form_kwargs(error=None):
    return dict(
        active="add",
        mode="add",
        item_id=None,
        item={},
        item_types=ITEM_TYPES,
        jewelry_subtypes=JEWELRY_SUBTYPES,
        color_suggestions=COLOR_SUGGESTIONS,
        season_suggestions=SEASON_SUGGESTIONS,
        sources=SOURCES,
        rating_min=RATING_MIN,
        rating_max=RATING_MAX,
        acquire_years=acquired_years(),
        acquire_months=ACQUIRED_MONTHS,
        error=error,
    )


@app.route("/add", methods=["GET", "POST"])
def add_item():
    if request.method == "POST":
        photo = request.files.get("photo")
        if not photo or not photo.filename:
            return render_template(
                "item_form.html", **_add_form_kwargs(error="Please choose a photo to upload.")
            ), 400

        new_id = next_item_id()

        from pipeline.process_images import get_session

        session = get_session()
        try:
            raw_rel, processed_rel = process_upload(photo, new_id, session)
        except ValueError as exc:
            return render_template(
                "item_form.html", **_add_form_kwargs(error=f"Couldn't process that photo: {exc}")
            ), 400

        new_item = _read_form_item(request.form)
        new_item["wear_count"] = 0
        new_item["images"] = [processed_rel]
        new_item["raw_images"] = [raw_rel]
        db.save_item(new_id, new_item)
        return redirect(url_for("item_view", item_id=new_id))

    return render_template("item_form.html", **_add_form_kwargs())


def _outfit_render_pieces(outfit: dict, items: dict) -> list[dict]:
    """Turn an outfit's raw x/y/w/rot layout into ready-to-draw percentages
    of the fixed board size, in the same order they're stacked on the
    board (later entries render on top) — used for both the outfits-list
    thumbnail and the edit page's starting arrangement."""
    pieces = []
    for placement in outfit.get("layout") or []:
        item = items.get(placement["id"])
        if item is None or not item.get("images"):
            continue
        filename = item["images"][0].split("/")[-1]
        pieces.append({
            "item_id": placement["id"],
            "src": url_for("photos", filename=filename),
            "thumb_src": thumb_url(item["images"][0]),
            "alt": item.get("name") or item.get("item_type") or "item",
            # Percentages of the fixed board size, for the outfits-list
            # thumbnail; raw px (the actual saved values) for reopening
            # this outfit in the builder to edit.
            "left_pct": placement["x"] / OUTFIT_BOARD_W * 100,
            "top_pct": placement["y"] / OUTFIT_BOARD_H * 100,
            "width_pct": placement["w"] / OUTFIT_BOARD_W * 100,
            "x": placement["x"],
            "y": placement["y"],
            "w": placement["w"],
            "rot": placement["rot"],
        })
    return pieces


@app.route("/outfits")
def outfits_list():
    items = db.load_items()
    outfits = db.load_outfits()
    for outfit in outfits:
        outfit["pieces"] = _outfit_render_pieces(outfit, items)
    return render_template("outfits_list.html", active="outfits", outfits=outfits)


@app.route("/outfits/new")
def outfit_builder():
    items = db.load_items()
    tray = [{"id": i, **items[i]} for i in sorted(items.keys())]
    return render_template(
        "outfit_builder.html", active="outfits", tray=tray, mode="new", outfit=None, initial_pieces=[]
    )


@app.route("/outfits/<outfit_id>/edit")
def edit_outfit(outfit_id):
    outfit = db.get_outfit(outfit_id)
    if outfit is None:
        abort(404)
    items = db.load_items()
    tray = [{"id": i, **items[i]} for i in sorted(items.keys())]
    return render_template(
        "outfit_builder.html",
        active="outfits",
        tray=tray,
        mode="edit",
        outfit=outfit,
        initial_pieces=_outfit_render_pieces(outfit, items),
    )


def _clean_placements(raw) -> list[dict] | None:
    """Coerce the board layout from a request into the exact shape the
    storage layer expects. Returns None if any entry is missing a field or
    has a non-numeric coordinate, so a malformed payload is a clean 400
    instead of a KeyError 500 deeper in."""
    if not isinstance(raw, list):
        return None
    cleaned = []
    for p in raw:
        try:
            cleaned.append({
                "id": str(p["id"]),
                "x": float(p["x"]),
                "y": float(p["y"]),
                "w": float(p["w"]),
                "rot": float(p["rot"]),
            })
        except (KeyError, TypeError, ValueError):
            return None
    return cleaned


def _outfit_payload_from_request():
    payload = request.get_json(force=True, silent=True) or {}
    placements = _clean_placements(payload.get("items") or [])
    if placements is None:
        return None, jsonify({"ok": False, "error": "malformed item placement"}), 400
    if not placements:
        return None, jsonify({"ok": False, "error": "no items placed"}), 400
    outfit = {
        "name": (payload.get("name") or "").strip() or "untitled outfit",
        "vibes": [v.strip() for v in (payload.get("vibes") or "").split(",") if v.strip()],
        "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "layout": placements,
    }
    return outfit, None, None


@app.route("/outfits", methods=["POST"])
def create_outfit():
    outfit, err_resp, err_code = _outfit_payload_from_request()
    if outfit is None:
        return err_resp, err_code
    outfit["id"] = db.next_outfit_id()
    db.save_outfit(outfit)
    return jsonify({"ok": True, "id": outfit["id"]})


@app.route("/outfits/<outfit_id>", methods=["POST"])
def update_outfit(outfit_id):
    if db.get_outfit(outfit_id) is None:
        abort(404)
    outfit, err_resp, err_code = _outfit_payload_from_request()
    if outfit is None:
        return err_resp, err_code
    outfit["id"] = outfit_id
    db.save_outfit(outfit)
    return jsonify({"ok": True, "id": outfit_id})


@app.route("/outfits/<outfit_id>/delete", methods=["POST"])
def delete_outfit(outfit_id):
    if db.get_outfit(outfit_id) is None:
        abort(404)
    db.delete_outfit(outfit_id)
    return redirect(url_for("outfits_list"))


def ensure_thumb(processed_filename: str) -> Path:
    """Build (or rebuild) the cached thumbnail for one processed cutout and
    return its path. Rebuilds whenever the source cutout is newer than the
    thumb, so a touched-up photo shows its new version."""
    from PIL import Image

    src = PROCESSED_DIR / processed_filename
    thumb = THUMBS_DIR / processed_filename
    if thumb.exists() and thumb.stat().st_mtime >= src.stat().st_mtime:
        return thumb

    THUMBS_DIR.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as im:
        im = im.convert("RGBA")
        im.thumbnail((THUMB_LONG_EDGE, THUMB_LONG_EDGE), Image.LANCZOS)
        im.save(thumb, format="PNG", optimize=True)
    return thumb


def thumb_url(image_path: str) -> str:
    """URL for a cached thumbnail of one processed cutout, cache-busted by
    the source file's own mtime. /thumbs/ is served with a 30-day browser
    cache (see the thumbs() route below) since the same filename is reused
    across touch-ups — without a version query param, a browser that had
    already cached the old thumbnail would keep showing it after a touch-up
    for the full 30 days, even though the server had already regenerated
    it (this is why an edit showed up on the item page's own /photos/ URL,
    which isn't cached this aggressively, but not on the closet grid)."""
    filename = image_path.split("/")[-1]
    src = PROCESSED_DIR / filename
    version = int(src.stat().st_mtime) if src.is_file() else 0
    return url_for("thumbs", filename=filename, v=version)


app.jinja_env.globals["thumb_url"] = thumb_url


@app.route("/thumbs/<path:filename>")
def thumbs(filename):
    # safe_join returns None on any attempt to escape the directory.
    from werkzeug.utils import safe_join

    safe = safe_join(str(PROCESSED_DIR), filename)
    if safe is None or not Path(safe).is_file():
        abort(404)
    ensure_thumb(filename)
    return send_from_directory(THUMBS_DIR, filename, max_age=60 * 60 * 24 * 30)


@app.route("/photos/<path:filename>")
def photos(filename):
    return send_from_directory(PROCESSED_DIR, filename)


if __name__ == "__main__":
    # Quiet down the per-request GET/POST access log lines; real errors
    # still show.
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    app.run(host="127.0.0.1", port=8000, debug=False)
