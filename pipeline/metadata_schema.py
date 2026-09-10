"""
Schema / controlled vocabulary for closet item metadata.

This is intentionally just Python data, not a database — items.json is the
source of truth and this file documents/validates what "valid" looks like.
Edit the *_OPTIONS lists as your closet reveals categories you didn't expect
(new item types, new vibes, etc.) — they're meant to grow.
"""

# Single-select — pick exactly one.
ITEM_TYPES = [
    "top", "bottom", "shorts", "pants", "skirt", "dress",
    "longsleeve", "tshirt", "tanktop", "jacket", "hoodie", "shoes", "accessory", "belt", "bag", "hat", "jewelry", "other",
]

SOURCES = [
    "thrifted", "new", "from mom", "gift", "from sat", "from bauer",
]

# 1 (bad) - 3 (great) rating fields.
RATING_FIELDS = ["comfort", "fit", "condition"]
RATING_MIN, RATING_MAX = 1, 3

# "Date acquired" is stored as "YYYY" or "YYYY-MM" (day is never known). The
# Add/Edit form's year dropdown starts here and runs to the current year.
ACQUIRED_MIN_YEAR = 2010

# Up to this many items can hold a gold star at once; awarding one past the
# cap drops the oldest star.
MAX_GOLD_STARS = 5

# Multi-select — pick any number. These lists are suggestions/starting
# points, not hard limits; feel free to use values outside them, the
# validator below only warns, it doesn't block.
COLOR_SUGGESTIONS = [
    "black", "white", "gray", "brown", "beige", "cream",
    "red", "orange", "yellow", "green", "blue", "purple", "pink", "multicolor",
]

SEASON_SUGGESTIONS = [
    "summer", "winter", "spring/fall", "all", "layering",
]

# Free-form tags — no suggested list, just an open vocabulary.
# Examples from the brief: "grunge", "daytime", "going out"
VIBES_EXAMPLES = ["grunge", "daytime", "going out"]

# Every field an item record can have. "required" fields being empty is what
# the validator flags as still-needs-filling-in.
REQUIRED_FIELDS = [
    "item_type", "color", "comfort", "fit", "condition",
    
]
OPTIONAL_FIELDS = ["name", "season", "wear_count", "notes", "vibes", "source", "price", "date_acquired"]
