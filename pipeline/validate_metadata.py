#!/usr/bin/env python3
"""
Check data/items.json against the schema in pipeline/metadata_schema.py.

Usage:
    python -m pipeline.validate_metadata
    python -m pipeline.validate_metadata --id 007      # just one item
    python -m pipeline.validate_metadata --summary      # counts only

Reports, per item: which required fields are still blank, and any values
that don't match the controlled vocab (item_type, source, rating range) —
those are warnings, not hard failures, since the *_OPTIONS lists are meant
to grow as your closet does.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .metadata_schema import (
    ITEM_TYPES,
    RATING_FIELDS,
    RATING_MAX,
    RATING_MIN,
    REQUIRED_FIELDS,
    SOURCES,
)

ITEMS_PATH = Path("data/items.json")


def is_blank(value) -> bool:
    return value is None or value == [] or value == ""


def check_item(item_id: str, item: dict) -> tuple[list[str], list[str]]:
    missing = [f for f in REQUIRED_FIELDS if is_blank(item.get(f))]

    warnings = []
    if item.get("item_type") not in (None, *ITEM_TYPES):
        warnings.append(f"item_type {item['item_type']!r} not in ITEM_TYPES (that's fine if intentional)")
    if item.get("source") not in (None, *SOURCES):
        warnings.append(f"source {item['source']!r} not in SOURCES (that's fine if intentional)")
    for field in RATING_FIELDS:
        val = item.get(field)
        if val is not None and not (RATING_MIN <= val <= RATING_MAX):
            warnings.append(f"{field}={val} outside {RATING_MIN}-{RATING_MAX} range")

    return missing, warnings


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--id", help="Check just one item ID (e.g. 007)")
    parser.add_argument("--summary", action="store_true", help="Print counts only, not per-item detail")
    args = parser.parse_args(argv)

    items = json.loads(ITEMS_PATH.read_text())

    ids = [args.id] if args.id else sorted(items)
    complete, incomplete = 0, 0

    for item_id in ids:
        if item_id not in items:
            print(f"?? {item_id}: not found in {ITEMS_PATH}")
            continue
        missing, warnings = check_item(item_id, items[item_id])
        if not missing:
            complete += 1
        else:
            incomplete += 1
        if args.summary:
            continue
        if missing or warnings:
            print(f"{item_id}:")
            if missing:
                print(f"   missing: {', '.join(missing)}")
            for w in warnings:
                print(f"   warning: {w}")
        else:
            print(f"{item_id}: OK")

    print(f"\n{complete}/{complete + incomplete} items fully filled in")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
