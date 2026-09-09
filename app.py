#!/usr/bin/env python3
"""
beck's closet — a tiny local web app, backed by a SQLite database
(data/closet.db).

Run it with:
    python3 app.py

Then open http://127.0.0.1:8000 in your browser.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from flask import Flask, abort, jsonify, redirect, render_template, request, send_from_directory, url_for

import db
from pipeline.metadata_schema import (
    COLOR_SUGGESTIONS,
    ITEM_TYPES,
    RATING_FIELDS,
    RATING_MAX,
    RATING_MIN,
    SEASON_SUGGESTIONS,
    SOURCES,
)

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
ORIGINALS_DIR = DATA_DIR / "originals"

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

def original_rel_for(processed_rel: str) -> str:
    """'data/processed/023_2.png' -> 'data/originals/023_2.png' — the
    untouched backup lives alongside processed/ under the same stub name."""
    return processed_rel.replace("data/processed/", "data/originals/", 1)


def ensure_original_backup(processed_rel: str) -> None:
    """Make sure an original-backup copy of a processed cutout exists.
    Normally this only ever runs once, right after upload — but it's also
    called lazily from the touch-up page so any item that predates this
    backup (or one whose backup went missing) still gets a valid one to
    reset to, taken from whatever's on disk right now."""
    from PIL import Image

    original_path = BASE_DIR / original_rel_for(processed_rel)
    if original_path.exists():
        return
    original_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(BASE_DIR / processed_rel) as im:
        im.save(original_path, format="PNG", optimize=True)


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
    ensure_original_backup(processed_rel)
    return f"data/raw/{stub}{raw_ext}", processed_rel


def cost_per_wear(item: dict):
    price, worn = item.get("price"), item.get("wear_count") or 0
    if price is None or not worn:
        return None
    return round(price / worn, 2)


def avg_rating(item: dict):
    vals = [item.get(f) for f in RATING_FIELDS if item.get(f)]
    return round(sum(vals) / len(vals)) if vals else 0


@app.context_processor
def inject_globals():
    total = db.count_items()
    return {"total_str": f"{total:03d}" if total < 1000 else str(total)}


# ------------------------------------------------------------------ views --

@app.route("/")
def closet():
    items = db.load_items()
    type_filter = request.args.get("type") or ""
    types_present = sorted({v.get("item_type") for v in items.values() if v.get("item_type")})

    cards = []
    for item_id in sorted(items.keys()):
        item = items[item_id]
        if type_filter and item.get("item_type") != type_filter:
            continue
        cards.append({"id": item_id, **item, "rating": avg_rating(item)})

    return render_template(
        "closet.html", active="closet", cards=cards, types=types_present, active_type=type_filter
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
    )


@app.route("/item/<item_id>/worn", methods=["POST"])
def mark_worn(item_id):
    if db.get_item(item_id) is None:
        abort(404)
    db.increment_wear_count(item_id)
    return redirect(url_for("item_view", item_id=item_id))


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

    return {
        "name": (form.get("name") or "").strip() or None,
        "item_type": form.get("item_type") or None,
        "color": multi("color"),
        "comfort": rating("comfort"),
        "fit": rating("fit"),
        "condition": rating("condition"),
        "vibes": vibes,
        "source": form.get("source") or None,
        "price": num("price"),
        "date_acquired": form.get("date_acquired") or None,
        "season": multi("season"),
        "notes": (form.get("notes") or "").strip(),
    }


def _edit_form_kwargs(item_id, item, error=None):
    return dict(
        active="closet",
        mode="edit",
        item_id=item_id,
        item=item,
        item_types=ITEM_TYPES,
        color_suggestions=COLOR_SUGGESTIONS,
        season_suggestions=SEASON_SUGGESTIONS,
        sources=SOURCES,
        rating_min=RATING_MIN,
        rating_max=RATING_MAX,
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
            from rembg import new_session

            from pipeline.config import REMBG_MODEL

            session = new_session(REMBG_MODEL)
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
            (BASE_DIR / original_rel_for(rel)).unlink(missing_ok=True)

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
    ensure_original_backup(processed_rel)
    return render_template(
        "touchup.html",
        active="closet",
        item_id=item_id,
        index=index,
        processed_filename=processed_rel.split("/")[-1],
        original_url=url_for("originals", filename=original_rel_for(processed_rel).split("/")[-1]),
    )


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
        color_suggestions=COLOR_SUGGESTIONS,
        season_suggestions=SEASON_SUGGESTIONS,
        sources=SOURCES,
        rating_min=RATING_MIN,
        rating_max=RATING_MAX,
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

        from rembg import new_session

        from pipeline.config import REMBG_MODEL

        session = new_session(REMBG_MODEL)
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
        pieces.append({
            "item_id": placement["id"],
            "src": url_for("photos", filename=item["images"][0].split("/")[-1]),
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


def _outfit_payload_from_request():
    import datetime

    payload = request.get_json(force=True, silent=True) or {}
    placements = payload.get("items") or []
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


@app.route("/photos/<path:filename>")
def photos(filename):
    return send_from_directory(PROCESSED_DIR, filename)


@app.route("/originals/<path:filename>")
def originals(filename):
    return send_from_directory(ORIGINALS_DIR, filename)


if __name__ == "__main__":
    # Quiet down the per-request GET/POST access log lines; real errors
    # still show.
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    app.run(host="127.0.0.1", port=8000, debug=False)
