#!/usr/bin/env python3
"""
beck's closet — a tiny local web app over data/items.json.

Run it with:
    python3 app.py

Then open http://127.0.0.1:8000 in your browser.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from flask import Flask, abort, jsonify, redirect, render_template, request, send_from_directory, url_for

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
ITEMS_PATH = DATA_DIR / "items.json"
OUTFITS_PATH = DATA_DIR / "outfits.json"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"

app = Flask(__name__)

# A handful of named colors get an actual swatch dot; anything else just
# shows as text without one.
COLOR_HEX = {
    "black": "#2b2140", "white": "#ffffff", "gray": "#9a94a6", "brown": "#7b5a3e",
    "beige": "#e4d3ae", "cream": "#f7efe0", "red": "#e0393e", "orange": "#f2884b",
    "yellow": "#ffd447", "green": "#5c9a63", "blue": "#5ec8e8", "purple": "#7c3aa0",
    "pink": "#ff6fa5", "multicolor": "conic-gradient(#e0393e,#ffd447,#5c9a63,#5ec8e8,#7c3aa0,#ff6fa5,#e0393e)",
}


# ---------------------------------------------------------------- storage --

def load_items() -> dict:
    with open(ITEMS_PATH) as f:
        return json.load(f)


def save_items(items: dict) -> None:
    with open(ITEMS_PATH, "w") as f:
        json.dump(items, f, indent=2, sort_keys=True)
        f.write("\n")


def load_outfits() -> list:
    with open(OUTFITS_PATH) as f:
        return json.load(f)


def save_outfits(outfits: list) -> None:
    with open(OUTFITS_PATH, "w") as f:
        json.dump(outfits, f, indent=2)
        f.write("\n")


def next_item_id(items: dict) -> str:
    existing = [int(k) for k in items.keys() if k.isdigit()]
    return f"{(max(existing) + 1) if existing else 1:03d}"


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
    total = len(load_items())
    return {"total_str": f"{total:03d}" if total < 1000 else str(total)}


# ------------------------------------------------------------------ views --

@app.route("/")
def closet():
    items = load_items()
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
    items = load_items()
    item = items.get(item_id)
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
    items = load_items()
    item = items.get(item_id)
    if item is None:
        abort(404)
    item["wear_count"] = int(item.get("wear_count") or 0) + 1
    save_items(items)
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


@app.route("/item/<item_id>/edit", methods=["GET", "POST"])
def edit_item(item_id):
    items = load_items()
    item = items.get(item_id)
    if item is None:
        abort(404)

    if request.method == "POST":
        updates = _read_form_item(request.form)
        updates["wear_count"] = item.get("wear_count") or 0
        updates["image"] = item.get("image")
        updates["raw_image"] = item.get("raw_image")
        items[item_id] = updates
        save_items(items)
        return redirect(url_for("item_view", item_id=item_id))

    return render_template(
        "item_form.html",
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
    )


@app.route("/add", methods=["GET", "POST"])
def add_item():
    items = load_items()

    if request.method == "POST":
        photo = request.files.get("photo")
        if not photo or not photo.filename:
            return render_template(
                "item_form.html",
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
                error="Please choose a photo to upload.",
            ), 400

        new_id = next_item_id(items)
        raw_ext = Path(photo.filename).suffix.lower() or ".jpg"
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        raw_path = RAW_DIR / f"{new_id}{raw_ext}"
        photo.save(raw_path)

        # Background removal + resize, reusing the same pipeline used for the
        # original batch import.
        from rembg import new_session

        from pipeline.config import OUTPUT_EXTENSION, REMBG_MODEL
        from pipeline.process_images import process_one

        session = new_session(REMBG_MODEL)
        result = process_one(raw_path, RAW_DIR, PROCESSED_DIR, session, overwrite=True)
        if result.status == "error":
            raw_path.unlink(missing_ok=True)
            return render_template(
                "item_form.html",
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
                error=f"Couldn't process that photo: {result.detail}",
            ), 400

        new_item = _read_form_item(request.form)
        new_item["wear_count"] = 0
        new_item["image"] = f"data/processed/{new_id}{OUTPUT_EXTENSION}"
        new_item["raw_image"] = f"data/raw/{new_id}{raw_ext}"
        items[new_id] = new_item
        save_items(items)
        return redirect(url_for("item_view", item_id=new_id))

    return render_template(
        "item_form.html",
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
        error=None,
    )


@app.route("/outfits")
def outfits_list():
    items = load_items()
    outfits = load_outfits()
    outfits = sorted(outfits, key=lambda o: o.get("created_at") or "", reverse=True)
    for outfit in outfits:
        outfit["pieces"] = [items[i] for i in outfit.get("item_ids", []) if i in items]
    return render_template("outfits_list.html", active="outfits", outfits=outfits)


@app.route("/outfits/new")
def outfit_builder():
    items = load_items()
    tray = [{"id": i, **items[i]} for i in sorted(items.keys())]
    return render_template("outfit_builder.html", active="outfits", tray=tray)


@app.route("/outfits", methods=["POST"])
def create_outfit():
    import datetime

    payload = request.get_json(force=True, silent=True) or {}
    placements = payload.get("items") or []
    if not placements:
        return jsonify({"ok": False, "error": "no items placed"}), 400

    outfits = load_outfits()
    outfit = {
        "id": f"o{len(outfits) + 1:04d}",
        "name": (payload.get("name") or "").strip() or "untitled outfit",
        "vibes": [v.strip() for v in (payload.get("vibes") or "").split(",") if v.strip()],
        "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "item_ids": [p["id"] for p in placements],
        "layout": placements,
    }
    outfits.append(outfit)
    save_outfits(outfits)
    return jsonify({"ok": True, "id": outfit["id"]})


@app.route("/photos/<path:filename>")
def photos(filename):
    return send_from_directory(PROCESSED_DIR, filename)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=False)
