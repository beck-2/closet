"""
SQLite storage layer for beck's closet.

Items and outfits used to live in flat JSON files (data/items.json,
data/outfits.json) that got rewritten *in full* on every save. Simple, but
with no real transactions — two overlapping saves could clobber each other
(and did, once, during development). This swaps that for a small SQLite
database (data/closet.db): same data, same shape once loaded into Python,
but every save is a real transaction that only touches the rows it's
actually changing.

The very first time the app runs against a fresh checkout (no closet.db
yet), it transparently imports whatever is in data/items.json and
data/outfits.json into the new database, then renames those files to
.json.bak so they're kept as a one-time backup but don't look like the
live data source anymore.
"""
from __future__ import annotations

import datetime
import json
import sqlite3
from pathlib import Path

from flask import g

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "closet.db"


def _db_path() -> Path:
    """The live SQLite file. Comes from app.config["DB_PATH"] when we're in a
    Flask app context (that's what lets a test point at its own temp DB), and
    falls back to the default location otherwise."""
    from flask import current_app, has_app_context

    if has_app_context() and "DB_PATH" in current_app.config:
        return Path(current_app.config["DB_PATH"])
    return DB_PATH

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS items (
    id            TEXT PRIMARY KEY,
    name          TEXT,
    item_type     TEXT,
    color         TEXT NOT NULL DEFAULT '[]',
    comfort       INTEGER,
    fit           INTEGER,
    condition     INTEGER,
    vibes         TEXT NOT NULL DEFAULT '[]',
    source        TEXT,
    price         REAL,
    date_acquired TEXT,
    season        TEXT NOT NULL DEFAULT '[]',
    wear_count    INTEGER NOT NULL DEFAULT 0,
    notes         TEXT NOT NULL DEFAULT '',
    sort_order    INTEGER
);

CREATE TABLE IF NOT EXISTS item_images (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id  TEXT NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    path     TEXT NOT NULL,
    raw_path TEXT,
    position INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_item_images_item ON item_images(item_id);

CREATE TABLE IF NOT EXISTS outfits (
    id         TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    vibes      TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS outfit_items (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    outfit_id TEXT NOT NULL REFERENCES outfits(id) ON DELETE CASCADE,
    item_id   TEXT NOT NULL,
    x         REAL NOT NULL,
    y         REAL NOT NULL,
    w         REAL NOT NULL,
    rot       REAL NOT NULL,
    position  INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_outfit_items_outfit ON outfit_items(outfit_id);

CREATE TABLE IF NOT EXISTS wear_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    worn_on    TEXT NOT NULL,              -- 'YYYY-MM-DD'
    item_id    TEXT NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    outfit_id  TEXT,                       -- set when this row came from logging a whole outfit
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_wear_log_date ON wear_log(worn_on);
CREATE INDEX IF NOT EXISTS idx_wear_log_item ON wear_log(item_id);

-- One optional comfort rating + notes per day, independent of what was
-- logged as worn. Both fields are optional; a day with neither set has no row.
CREATE TABLE IF NOT EXISTS day_log (
    worn_on TEXT PRIMARY KEY,
    comfort INTEGER,
    notes   TEXT NOT NULL DEFAULT ''
);

-- The day's ad-hoc arrangement of loose (non-outfit) pieces on the same
-- fixed board used by outfits — same x/y/w/rot shape as outfit_items, keyed
-- by date instead of an outfit id. Saving this is also what logs/unlogs
-- those pieces as worn that day (see db.save_day_layout).
CREATE TABLE IF NOT EXISTS day_layout (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    worn_on  TEXT NOT NULL,
    item_id  TEXT NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    x        REAL NOT NULL,
    y        REAL NOT NULL,
    w        REAL NOT NULL,
    rot      REAL NOT NULL,
    position INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_day_layout_date ON day_layout(worn_on);
"""


def _migrate_items_json(db: sqlite3.Connection, items_json: Path) -> int:
    items = json.loads(items_json.read_text())
    for item_id, item in items.items():
        db.execute(
            """INSERT INTO items (id, name, item_type, color, comfort, fit, condition,
                                   vibes, source, price, date_acquired, season, wear_count, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                item_id, item.get("name"), item.get("item_type"),
                json.dumps(item.get("color") or []),
                item.get("comfort"), item.get("fit"), item.get("condition"),
                json.dumps(item.get("vibes") or []),
                item.get("source"), item.get("price"), item.get("date_acquired"),
                json.dumps(item.get("season") or []),
                item.get("wear_count") or 0,
                item.get("notes") or "",
            ),
        )
        images = item.get("images") or []
        raws = item.get("raw_images") or []
        for pos, path in enumerate(images):
            raw = raws[pos] if pos < len(raws) else None
            db.execute(
                "INSERT INTO item_images (item_id, path, raw_path, position) VALUES (?, ?, ?, ?)",
                (item_id, path, raw, pos),
            )
    items_json.rename(items_json.with_suffix(".json.bak"))
    return len(items)


def _migrate_outfits_json(db: sqlite3.Connection, outfits_json: Path) -> int:
    outfits = json.loads(outfits_json.read_text())
    for outfit in outfits:
        db.execute(
            "INSERT INTO outfits (id, name, vibes, created_at) VALUES (?, ?, ?, ?)",
            (
                outfit["id"],
                outfit.get("name") or "untitled outfit",
                json.dumps(outfit.get("vibes") or []),
                outfit.get("created_at") or "",
            ),
        )
        for pos, placement in enumerate(outfit.get("layout") or []):
            db.execute(
                """INSERT INTO outfit_items (outfit_id, item_id, x, y, w, rot, position)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    outfit["id"], placement["id"], placement["x"], placement["y"],
                    placement["w"], placement["rot"], pos,
                ),
            )
    outfits_json.rename(outfits_json.with_suffix(".json.bak"))
    return len(outfits)


def init_db(db_path: Path | None = None) -> None:
    """Create the schema if it doesn't exist yet, and one-time import old
    JSON data the first time this runs against a fresh database. The old
    items.json/outfits.json are looked for next to the database file."""
    db_path = Path(db_path) if db_path is not None else _db_path()
    data_dir = db_path.parent
    items_json = data_dir / "items.json"
    outfits_json = data_dir / "outfits.json"

    is_new = not db_path.exists()
    data_dir.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(db_path)
    try:
        db.executescript(SCHEMA_SQL)
        # Columns added after the first schema shipped — for databases created
        # before them. Cheap, idempotent, runs every startup.
        have = {row[1] for row in db.execute("PRAGMA table_info(items)")}
        if "sort_order" not in have:
            db.execute("ALTER TABLE items ADD COLUMN sort_order INTEGER")
        if is_new:
            if items_json.exists():
                n = _migrate_items_json(db, items_json)
                print(f"[closet] migrated {n} item(s) from data/items.json into {db_path.name}")
            if outfits_json.exists():
                n = _migrate_outfits_json(db, outfits_json)
                print(f"[closet] migrated {n} outfit(s) from data/outfits.json into {db_path.name}")
        db.commit()
    finally:
        db.close()


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(_db_path())
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(exception=None) -> None:
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


# ---------------------------------------------------------------- items --

def _item_from_row(db: sqlite3.Connection, row: sqlite3.Row) -> dict:
    images, raw_images = [], []
    for img in db.execute(
        "SELECT path, raw_path FROM item_images WHERE item_id = ? ORDER BY position", (row["id"],)
    ):
        images.append(img["path"])
        raw_images.append(img["raw_path"])
    # wear_count is derived from the calendar (wear_log), not stored on the row.
    wear_count = db.execute(
        "SELECT COUNT(*) FROM wear_log WHERE item_id = ?", (row["id"],)
    ).fetchone()[0]
    return {
        "id": row["id"],
        "name": row["name"],
        "item_type": row["item_type"],
        "color": json.loads(row["color"]),
        "comfort": row["comfort"],
        "fit": row["fit"],
        "condition": row["condition"],
        "vibes": json.loads(row["vibes"]),
        "source": row["source"],
        "price": row["price"],
        "date_acquired": row["date_acquired"],
        "season": json.loads(row["season"]),
        "wear_count": wear_count,
        "notes": row["notes"],
        "sort_order": row["sort_order"],
        "images": images,
        "raw_images": raw_images,
    }


# Manually-ordered items first (by sort_order), then anything never dragged,
# oldest id first. That "unset goes last" is what keeps a brand-new item at
# the end until you place it.
_ITEM_ORDER = "ORDER BY sort_order IS NULL, sort_order, id"


def load_items() -> dict:
    db = get_db()
    return {row["id"]: _item_from_row(db, row) for row in db.execute(f"SELECT * FROM items {_ITEM_ORDER}")}


def get_item(item_id: str) -> dict | None:
    db = get_db()
    row = db.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    return _item_from_row(db, row) if row else None


def count_items() -> int:
    return get_db().execute("SELECT COUNT(*) FROM items").fetchone()[0]


def existing_item_ids() -> list[str]:
    return [row["id"] for row in get_db().execute("SELECT id FROM items")]


def save_item(item_id: str, item: dict) -> None:
    """Insert or fully replace one item's row + its photo rows, in one
    transaction. Doesn't touch any other item."""
    db = get_db()
    db.execute(
        """INSERT INTO items (id, name, item_type, color, comfort, fit, condition, vibes,
                               source, price, date_acquired, season, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(id) DO UPDATE SET
             name=excluded.name, item_type=excluded.item_type, color=excluded.color,
             comfort=excluded.comfort, fit=excluded.fit, condition=excluded.condition,
             vibes=excluded.vibes, source=excluded.source, price=excluded.price,
             date_acquired=excluded.date_acquired, season=excluded.season,
             notes=excluded.notes""",
        (
            item_id, item.get("name"), item.get("item_type"),
            json.dumps(item.get("color") or []),
            item.get("comfort"), item.get("fit"), item.get("condition"),
            json.dumps(item.get("vibes") or []),
            item.get("source"), item.get("price"), item.get("date_acquired"),
            json.dumps(item.get("season") or []),
            item.get("notes") or "",
        ),
    )
    db.execute("DELETE FROM item_images WHERE item_id = ?", (item_id,))
    images = item.get("images") or []
    raw_images = item.get("raw_images") or []
    for pos, path in enumerate(images):
        raw = raw_images[pos] if pos < len(raw_images) else None
        db.execute(
            "INSERT INTO item_images (item_id, path, raw_path, position) VALUES (?, ?, ?, ?)",
            (item_id, path, raw, pos),
        )
    db.commit()


def set_closet_order(ordered_ids: list[str]) -> None:
    """Stamp sort_order = 0, 1, 2, … onto the items in the given order. Ids
    that aren't real items are ignored."""
    db = get_db()
    known = {row["id"] for row in db.execute("SELECT id FROM items")}
    for pos, item_id in enumerate(i for i in ordered_ids if i in known):
        db.execute("UPDATE items SET sort_order = ? WHERE id = ?", (pos, item_id))
    db.commit()


# ------------------------------------------------------- calendar / wear --
# wear_log is the single source of truth for "what was worn when". A logged
# outfit is stored as one row per piece with outfit_id set; a loose item is
# one row with outfit_id NULL. Every item's wear_count derives from here.

def _now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def log_items_worn(worn_on: str, item_ids: list[str]) -> None:
    db = get_db()
    known = {row["id"] for row in db.execute("SELECT id FROM items")}
    for item_id in item_ids:
        if item_id not in known:
            continue
        already = db.execute(
            "SELECT 1 FROM wear_log WHERE worn_on = ? AND item_id = ? AND outfit_id IS NULL",
            (worn_on, item_id),
        ).fetchone()
        if already:
            continue
        db.execute(
            "INSERT INTO wear_log (worn_on, item_id, outfit_id, created_at) VALUES (?, ?, NULL, ?)",
            (worn_on, item_id, _now()),
        )
    db.commit()


def log_outfit_worn(worn_on: str, outfit_id: str) -> None:
    db = get_db()
    if db.execute("SELECT 1 FROM outfits WHERE id = ?", (outfit_id,)).fetchone() is None:
        return
    db.execute(
        "DELETE FROM wear_log WHERE worn_on = ? AND outfit_id = ?", (worn_on, outfit_id)
    )
    for r in db.execute(
        "SELECT DISTINCT item_id FROM outfit_items WHERE outfit_id = ?", (outfit_id,)
    ):
        db.execute(
            "INSERT INTO wear_log (worn_on, item_id, outfit_id, created_at) VALUES (?, ?, ?, ?)",
            (worn_on, r["item_id"], outfit_id, _now()),
        )
    db.commit()


def unlog_item(worn_on: str, item_id: str) -> None:
    db = get_db()
    db.execute(
        "DELETE FROM wear_log WHERE worn_on = ? AND item_id = ? AND outfit_id IS NULL",
        (worn_on, item_id),
    )
    db.commit()


def unlog_outfit(worn_on: str, outfit_id: str) -> None:
    db = get_db()
    db.execute(
        "DELETE FROM wear_log WHERE worn_on = ? AND outfit_id = ?", (worn_on, outfit_id)
    )
    db.commit()


def get_day_layout(worn_on: str) -> list[dict]:
    """The day's ad-hoc board arrangement, in stacking order — same shape as
    an outfit's layout."""
    return [
        {"id": r["item_id"], "x": r["x"], "y": r["y"], "w": r["w"], "rot": r["rot"]}
        for r in get_db().execute(
            "SELECT * FROM day_layout WHERE worn_on = ? ORDER BY position", (worn_on,)
        )
    ]


def save_day_layout(worn_on: str, placements: list[dict]) -> None:
    """Replace the day's ad-hoc board arrangement, and keep wear_log's loose
    (non-outfit) rows for that date in sync with what's actually on the
    board — placing a piece logs it worn that day, removing it un-logs it."""
    db = get_db()
    known = {row["id"] for row in db.execute("SELECT id FROM items")}
    cleaned = [p for p in placements if p["id"] in known]

    keep_ids = {p["id"] for p in cleaned}
    currently_loose = {
        r["item_id"] for r in db.execute(
            "SELECT item_id FROM wear_log WHERE worn_on = ? AND outfit_id IS NULL", (worn_on,)
        )
    }
    for item_id in currently_loose - keep_ids:
        db.execute(
            "DELETE FROM wear_log WHERE worn_on = ? AND item_id = ? AND outfit_id IS NULL",
            (worn_on, item_id),
        )
    for item_id in keep_ids - currently_loose:
        db.execute(
            "INSERT INTO wear_log (worn_on, item_id, outfit_id, created_at) VALUES (?, ?, NULL, ?)",
            (worn_on, item_id, _now()),
        )

    db.execute("DELETE FROM day_layout WHERE worn_on = ?", (worn_on,))
    for pos, p in enumerate(cleaned):
        db.execute(
            "INSERT INTO day_layout (worn_on, item_id, x, y, w, rot, position) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (worn_on, p["id"], p["x"], p["y"], p["w"], p["rot"], pos),
        )
    db.commit()


def wears_on(worn_on: str) -> dict:
    """What was worn on one day: loose items and whole outfits, each fully
    hydrated."""
    db = get_db()
    items = [
        get_item(r["item_id"])
        for r in db.execute(
            "SELECT item_id FROM wear_log WHERE worn_on = ? AND outfit_id IS NULL ORDER BY id",
            (worn_on,),
        )
    ]
    outfit_ids = [
        r["outfit_id"]
        for r in db.execute(
            "SELECT DISTINCT outfit_id FROM wear_log WHERE worn_on = ? AND outfit_id IS NOT NULL ORDER BY outfit_id",
            (worn_on,),
        )
    ]
    return {
        "items": [it for it in items if it],
        "outfits": [o for o in (get_outfit(oid) for oid in outfit_ids) if o],
    }


def wear_summary_for_month(year: int, month: int) -> dict:
    """{ 'YYYY-MM-DD': {'item_ids': [...], 'outfit_ids': [...]} } for every day
    in the month that has anything logged."""
    db = get_db()
    like = f"{year:04d}-{month:02d}-%"
    out: dict = {}
    for r in db.execute(
        "SELECT worn_on, item_id, outfit_id FROM wear_log WHERE worn_on LIKE ? ORDER BY id",
        (like,),
    ):
        day = out.setdefault(r["worn_on"], {"item_ids": [], "outfit_ids": []})
        if r["outfit_id"]:
            if r["outfit_id"] not in day["outfit_ids"]:
                day["outfit_ids"].append(r["outfit_id"])
        elif r["item_id"] not in day["item_ids"]:
            day["item_ids"].append(r["item_id"])
    return out


def wear_counts() -> dict:
    """{item_id: number of days it was worn} for every item that has any."""
    return {
        r["item_id"]: r["n"]
        for r in get_db().execute(
            "SELECT item_id, COUNT(DISTINCT worn_on) AS n FROM wear_log GROUP BY item_id"
        )
    }


def items_worn_since(cutoff: str) -> set[str]:
    """Set of item ids worn on or after `cutoff` (a 'YYYY-MM-DD' string)."""
    return {
        r["item_id"]
        for r in get_db().execute(
            "SELECT DISTINCT item_id FROM wear_log WHERE worn_on >= ?", (cutoff,)
        )
    }


def last_worn(item_id: str) -> str | None:
    row = get_db().execute(
        "SELECT MAX(worn_on) AS d FROM wear_log WHERE item_id = ?", (item_id,)
    ).fetchone()
    return row["d"] if row else None


def get_day_log(worn_on: str) -> dict:
    row = get_db().execute(
        "SELECT comfort, notes FROM day_log WHERE worn_on = ?", (worn_on,)
    ).fetchone()
    return {"comfort": row["comfort"], "notes": row["notes"]} if row else {"comfort": None, "notes": ""}


def save_day_log(worn_on: str, comfort: int | None, notes: str) -> None:
    """Optional per-day comfort rating + notes. Saving with both empty clears
    the row rather than leaving a blank one behind."""
    db = get_db()
    notes = (notes or "").strip()
    if comfort is None and not notes:
        db.execute("DELETE FROM day_log WHERE worn_on = ?", (worn_on,))
    else:
        db.execute(
            """INSERT INTO day_log (worn_on, comfort, notes) VALUES (?, ?, ?)
               ON CONFLICT(worn_on) DO UPDATE SET comfort=excluded.comfort, notes=excluded.notes""",
            (worn_on, comfort, notes),
        )
    db.commit()


# -------------------------------------------------------------- outfits --

def load_outfits() -> list[dict]:
    db = get_db()
    outfits = []
    for row in db.execute("SELECT * FROM outfits ORDER BY created_at DESC"):
        layout = [
            {"id": r["item_id"], "x": r["x"], "y": r["y"], "w": r["w"], "rot": r["rot"]}
            for r in db.execute(
                "SELECT * FROM outfit_items WHERE outfit_id = ? ORDER BY position", (row["id"],)
            )
        ]
        outfits.append({
            "id": row["id"],
            "name": row["name"],
            "vibes": json.loads(row["vibes"]),
            "created_at": row["created_at"],
            "item_ids": [p["id"] for p in layout],
            "layout": layout,
        })
    return outfits


def next_outfit_id() -> str:
    count = get_db().execute("SELECT COUNT(*) FROM outfits").fetchone()[0]
    return f"o{count + 1:04d}"


def get_outfit(outfit_id: str) -> dict | None:
    db = get_db()
    row = db.execute("SELECT * FROM outfits WHERE id = ?", (outfit_id,)).fetchone()
    if row is None:
        return None
    layout = [
        {"id": r["item_id"], "x": r["x"], "y": r["y"], "w": r["w"], "rot": r["rot"]}
        for r in db.execute(
            "SELECT * FROM outfit_items WHERE outfit_id = ? ORDER BY position", (outfit_id,)
        )
    ]
    return {
        "id": row["id"],
        "name": row["name"],
        "vibes": json.loads(row["vibes"]),
        "created_at": row["created_at"],
        "item_ids": [p["id"] for p in layout],
        "layout": layout,
    }


def save_outfit(outfit: dict) -> None:
    """Insert or fully replace one outfit's row + its layout rows, in one
    transaction — works for both a brand-new outfit and an edit of an
    existing one. On an update, the original created_at is left alone."""
    db = get_db()
    db.execute(
        """INSERT INTO outfits (id, name, vibes, created_at) VALUES (?, ?, ?, ?)
           ON CONFLICT(id) DO UPDATE SET name=excluded.name, vibes=excluded.vibes""",
        (outfit["id"], outfit["name"], json.dumps(outfit.get("vibes") or []), outfit.get("created_at") or ""),
    )
    db.execute("DELETE FROM outfit_items WHERE outfit_id = ?", (outfit["id"],))
    for pos, placement in enumerate(outfit.get("layout") or []):
        db.execute(
            "INSERT INTO outfit_items (outfit_id, item_id, x, y, w, rot, position) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                outfit["id"], placement["id"], placement["x"], placement["y"],
                placement["w"], placement["rot"], pos,
            ),
        )
    db.commit()


def delete_outfit(outfit_id: str) -> None:
    """Removes the outfit row; outfit_items rows cascade via the FK."""
    db = get_db()
    db.execute("DELETE FROM outfits WHERE id = ?", (outfit_id,))
    db.commit()
