# Windrose Save Editor — CLAUDE.md

## What this project is

A save editor for the game **Windrose** (Steam/Epic, internal name R5).
Save files are RocksDB databases containing BSON-encoded player documents.
Wiki: https://windrose.wiki.fextralife.com/Windrose_Wiki

---

## NEVER (save-editor-specific hard rules)

### NEVER write to a save without a backup first
`save_backup()` must be called before `commit_changes()`. The `SaveSession.backed_up`
flag tracks this. Do not bypass it.

### NEVER modify the existing WAL file
Only write a NEW `.log` file with a higher number than the current one.
Writing to the existing WAL causes an infinite loading screen because RocksDB
considers that data already applied.

### NEVER skip the BSON round-trip check
`serialize_bson_doc(parse_bson(original_bytes))` must equal `original_bytes`
byte-for-byte when no changes were made. This check lives in `commit_changes()`
and is the primary safeguard against silent data corruption.

### NEVER commit real save file data
Tests must build synthetic BSON docs from scratch. No real player save files
in the repo, ever.

### NEVER put input() or print() outside cli.py
`editors/`, `inventory/`, `rocksdb/`, `save/`, `bson/` are UI-free service layers.
All user I/O lives in `cli.py` only. This is what makes a future GUI possible
without rewriting business logic.

### NEVER write to column families other than CF 2
CF 0 = default, CF 1 = R5LargeObjects, **CF 2 = R5BLPlayer (player data)**,
CF 3 = R5BLShip, CF 4 = R5BLBuilding, CF 5 = R5BLActor_BuildingBlock.

---

## Architecture

```
windrose_save_editor/
├── bson/         pure Python, no I/O, no platform deps — safe to import anywhere
├── crc.py        pure Python
├── rocksdb/      RocksDB WAL/SST/manifest — no UI
├── save/         backup, commit, location — no UI
├── inventory/    item reader (ItemRecord TypedDict) + writer — no UI
├── editors/      stat + skill service functions — no UI
├── game_data.py  static lookup tables only
├── process.py    OS-level game process utilities
└── cli.py        ALL user I/O lives here — thin wrappers over the service layer
```

The CLI and any future GUI are both just **frontends** that call the same service layer.

---

## Platform-specific code

`msvcrt`, `rocksdb.dll`, `librocksdb.so` are platform-specific. Any such import
must be wrapped in `try/except ImportError` or a `sys.platform` check so the
module imports cleanly everywhere. The test suite runs on Linux (CI) — it must
not require Windows.

---

## Quality gates (from global, applied here)

- Tests must pass before every commit: `pytest`
- No function > 50 lines — extract helpers
- TDD-first: write the test before the implementation
- Full type hints on all public functions — no bare `dict`, use `BSONDoc`, `ItemRecord`, etc.
- No bare `except:` — always `except Exception` or more specific
- `from __future__ import annotations` at the top of every module

### Known exception to the 300-line file rule
`cli.py` (~767 lines) is intentionally large — it is the complete interactive menu.
Only split it if adding a major new feature area (e.g. a web UI layer).

---

## Versioning

Format: `major.minor` — e.g. `1.2`, never `1.2.0`.
Update `windrose_save_editor/__init__.py` and `pyproject.toml` together.
Current release on Nexus Mods: `1.1b`.

---

## Running locally

```bash
pip install -e ".[dev]"   # install with dev deps
pytest                     # run all tests
python -m windrose_save_editor <save_path>   # run the editor
./scripts/build-release.sh                   # build the Nexus zip
```
