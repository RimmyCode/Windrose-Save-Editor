# Contributing to Windrose Save Editor

---

## The short version — read this first

Copy-paste these commands. Do this every time you work on the project.

### Step 1 — Activate your virtual environment (once per terminal session)

**Windows:**
```
.venv\Scripts\activate
```
**Mac / Linux:**
```
source .venv/bin/activate
```
You'll see `(.venv)` appear at the start of your prompt. If it's already there, skip this.

---

### Step 2 — Before you change anything, make sure tests are green

```
pytest
```
You should see **45 passed**. If something is already broken before you touched it, stop and flag it.

---

### Step 3 — Write a failing test first

Open the relevant test file in `tests/` and add a test for the thing you're about to build.
Run it:
```
pytest tests/test_inventory.py   ← swap for whichever file matches your change
```
It should **fail** right now. That's correct. You haven't written the code yet.

---

### Step 4 — Write the code that makes the test pass

Make the change in the right module (see the **Project tour** section below for where things live).
Then run the failing test again until it goes green.

---

### Step 5 — Run the full suite to make sure you didn't break anything

```
pytest
```
Must show **45 passed** (or more, if you added new tests). Zero failures, zero errors.
If something broke that you didn't touch — fix it before committing.

---

### Step 6 — Commit your changes

Stage the files you changed:
```
git add windrose_save_editor/inventory/writer.py tests/test_inventory.py
```
Write a commit message that says *what* changed and *why* in one line:
```
git commit -m "fix: blank_item was hardcoding ItemId instead of generating a new GUID"
```

---

### Step 7 — Push and open a PR

```
git push
```
Then go to GitHub and open a Pull Request against `main`. Keep the PR to one logical change.
CI will run the tests on Python 3.10–3.13 automatically — wait for it to go green before asking for a review.

---

### Building the release zip (for Nexus Mods)

```
./scripts/build-release.sh
```
Output: `dist/windrose-save-editor-1.1b.zip`

---

### Building the standalone exe (for users without Python)

```
pip install -e ".[build]"
./scripts/build-exe.sh
```
Output: `dist/windrose-save-editor-1.1b-exe.zip`
Put `rocksdb.dll` (Windows) or `librocksdb.so` (Linux) next to `windrose.spec` before running if you want SST fallback bundled in.

---


Welcome. This guide walks you through how the project is structured, how to
make a change the right way, and what to keep in mind before opening a PR.

---

## Project tour

Before touching any code, read this once so nothing surprises you.

```
windrose_save_editor/
├── bson/         Parse and serialize BSON (pure Python, no deps, no I/O)
│   ├── types.py  — BSONDoc, BSONArray, BSONInt64, BSONDatetime type defs
│   ├── parser.py — parse_bson(bytes) → dict
│   └── serializer.py — serialize_bson_doc(dict) → bytes
│
├── rocksdb/      Read and write RocksDB databases
│   ├── wal.py    — read_wal / write_wal (WAL = Write-Ahead Log)
│   ├── manifest.py — parse_manifest (reads sequence numbers)
│   └── sst.py    — scan_sst_for_player (ctypes C API, Windows/Linux DLL)
│
├── save/         Everything to do with a save session
│   ├── location.py — find the player save folder automatically
│   ├── backup.py   — create and restore backups
│   └── commit.py   — SaveSession, commit_changes (waits for game exit, writes WAL)
│
├── inventory/    Item reading and writing
│   ├── reader.py — get_all_items(doc) → list[ItemRecord]
│   └── writer.py — blank_item / blank_slot_with_item
│
├── editors/      Stat and skill editing — no UI, fully testable
│   ├── stats.py  — get_stats / set_stat_level
│   └── skills.py — get_skills / set_skill_level
│
├── crc.py        CRC32C (Castagnoli) — used by RocksDB checksums
├── game_data.py  Talent names, descriptions, stat names — static tables only
├── process.py    Game process detection and shutdown (uses psutil)
└── cli.py        ALL user I/O lives here — thin wrapper over the service layer
```

**The one rule that holds everything together:** `cli.py` is the only place
`input()` and `print()` are allowed. Everything else is a pure service function
that takes data in and returns data out. This is what makes the editor testable
and what makes a future GUI possible without rewriting any logic.

---

## Getting set up

```bash
git clone https://github.com/RimmyCode/Windrose-Save-Editor.git
cd Windrose-Save-Editor
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest
```

You should see **45 tests pass** in under a second. If they all go green you're ready.

---

## Making a change — step by step

### 1. Write a failing test first

Find the test file for the module you're changing (or create one under `tests/`).
Write a test that describes the behavior you want — it should fail right now.

```bash
pytest tests/test_inventory.py   # run just the relevant file
```

A few rules for tests:
- Build BSON documents synthetically in the test — **never use real save files**
- Import only from `windrose_save_editor.*` — no internal private helpers
- Assert something meaningful; "it didn't crash" is not a test

### 2. Implement the change

Put the code in the right module (see the tour above).

- Editing how stats work? → `editors/stats.py`
- New item writing logic? → `inventory/writer.py`
- New menu option? → `cli.py` only — wire it to an existing service function
- New game constant (talent name, stat name)? → `game_data.py`

**Type hints are required** on all public functions:

```python
def set_stat_level(doc: BSONDoc, node_key: str, level: int) -> None: ...
```

**No bare `except:`** — always `except Exception` or something more specific.

### 3. Run the full test suite

```bash
pytest
```

All 45 tests must stay green. If you broke something unrelated, fix it — don't
paper over it.

### 4. Check the architecture hasn't drifted

Before committing, ask yourself:

- Did I add any `input()` or `print()` outside `cli.py`? → Move it.
- Did I import anything from `cli.py` into a service module? → Invert the dependency.
- Did I use a real save file in a test? → Replace it with a synthetic doc.
- Did I write to any column family other than CF 2 (R5BLPlayer)? → Revert it.

### 5. Open a PR

- Target branch: `main`
- PR title: one line describing what changed and why
- Keep the diff focused — one logical change per PR
- CI runs on Python 3.10–3.13; if it goes red, fix it before asking for review

---

## What belongs where — quick reference

| What you're adding | Where it goes |
|--------------------|---------------|
| New stat or skill editing logic | `editors/stats.py` or `editors/skills.py` |
| New item type or item construction | `inventory/writer.py` |
| New item scanning / reading | `inventory/reader.py` |
| New BSON type or parsing rule | `bson/parser.py` or `bson/types.py` |
| New game constant (talent name, etc.) | `game_data.py` |
| User-facing menu or prompt | `cli.py` only |
| Save path detection or backup | `save/location.py` or `save/backup.py` |
| RocksDB format change | `rocksdb/wal.py` or `rocksdb/manifest.py` |

---

## Versioning

Format is `major.minor` — e.g. `1.2`, never `1.2.0`.
Update `windrose_save_editor/__init__.py` and `pyproject.toml` together.
Current release: `1.1b`.
