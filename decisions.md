# decisions

Why things are built the way they are. Newest first.

## Test harness + configurable DB path (2026-09-09)

**What:** Added `pytest`, a `tests/` suite, and made the SQLite path come from
`app.config["DB_PATH"]` (overridable via the `CLOSET_DB_PATH` env var) instead
of a hardcoded module constant.

**Why:** `db.py` hardcoded `DB_PATH` and `app.py` called `db.init_db()` at
import time, so there was no way to point the app at a throwaway database for a
test. Threading a config value through `get_db()` / `init_db()` is the smallest
change that makes each test able to run against its own fresh temp DB.

**Why not a full `create_app()` factory / blueprint:** it would mean reindenting
every route and rewriting every `url_for()` in the templates (`closet` ->
`main.closet`). Big, risky diff for little gain right now. The config hook gets
us testable; we can promote to a real factory later if a step actually needs it.
