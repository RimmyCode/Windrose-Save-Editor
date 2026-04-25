# Windrose Save Editor

A Python-based save editor for the game **Windrose**, capable of reading and writing character save files directly. Edit your inventory items, character stats, and talent skills without touching any game files other than your own save data.

> **Nexus Mods page:** https://www.nexusmods.com/windrose/mods/153

---

## Features

- **Inventory management** — View all items across all inventory modules, set item levels, set stack counts, add new items, or replace existing ones with a different variant
- **Stat editor** — Edit the six core stats (Strength, Agility, Precision, Mastery, Vitality, Endurance) with automatic ProgressionPoints recalculation
- **Skill editor** — Edit all 37 talent nodes across all four skill trees (Fencer, Toughguy, Marksman, Crusher), with skill descriptions and auto-creation of nodes not yet unlocked
- **Safe saving workflow** — Waits for a clean game exit before writing, creates a full automatic backup on first save, and verifies the written WAL before completion
- **Backup & restore** — Full save root backups (Accounts + Players + Worlds), with a restore option built directly into the editor
- **Auto-detect** — Automatically locates your save folder on Windows and Linux/Proton without needing to pass a path manually
- **JSON export** — Dumps the full save document as readable JSON for inspection or community sharing
- **No dependencies required** — Pure Python standard library for all core functionality; `psutil` is optional for game process detection

---

## Requirements

- Python 3.10 or newer
- `psutil` — optional, enables auto-detection and force-close of the game process
  ```
  pip install psutil
  ```

---

## Quick Start

### Auto-detect (recommended)

Run the script with no arguments and it will find your save automatically:

```bash
python Windrose_Save_Editor.py
```

If you have multiple characters, you will be prompted to choose one.

### Manual path

```bash
python Windrose_Save_Editor.py "C:\Users\YourName\AppData\Local\R5\Saved\SaveProfiles\<SteamID>\RocksDB\0.10.0\Players\<CharacterGUID>"
```

You can also pass a parent folder — the editor will search downward to find the correct player save directory.

---

## Save Location

**Windows:**
```
%LOCALAPPDATA%\R5\Saved\SaveProfiles\<SteamID>\RocksDB\0.10.0\Players\<CharacterGUID>\
```

**Linux (Proton):**
```
~/.local/share/Steam/steamapps/compatdata/3041230/pfx/drive_c/users/steamuser/AppData/Local/R5/Saved/SaveProfiles/
```

---

## Usage

Once the editor loads your save, a numbered menu is presented. All edits are held in memory until you explicitly press **S** to save. A full automatic backup is created before the first write of each session.

See **[GUIDE.md](GUIDE.md)** for a complete walkthrough of every feature.

---

## How It Works

Windrose stores character data in a **RocksDB** database. The active player record is a **BSON** document written into the database's Write-Ahead Log (WAL). This editor:

1. Reads and parses the WAL (or SST files via the RocksDB C API if the WAL is empty)
2. Deserialises the BSON document into a Python dictionary
3. Applies your changes in memory
4. Serialises the document back to BSON
5. Waits for a clean game exit, then writes the modified data as a new WAL entry
6. Verifies the written WAL by reading it back before finishing

The BSON parser and serialiser are implemented from scratch in pure Python to ensure exact round-trip fidelity, preserving all type information (arrays, datetimes, int64, binary blobs).

---

## ⚠ Important Warnings

- **Always back up your save before editing.** The editor creates an automatic backup, but having your own copy is strongly recommended.
- **Quit the game via the in-game menu (Esc → Quit) running the script.** A hard kill (Alt+F4, Task Manager) can leave the database in a partially written state that may conflict with the editor's output.
- **Using incorrect ItemParams paths can result in broken or corrupted saves.** The can be found using the included Item ID Database.html

---

## Development

### Setup

```bash
git clone <repo>
cd Windrose-Save-Editor
pip install -e ".[dev]"
```

### Running Tests

```bash
pytest
```

### Project Structure

```
windrose_save_editor/
├── bson/          # BSON parser and serializer (pure Python, no deps)
├── rocksdb/       # RocksDB WAL/SST/manifest read+write
├── save/          # Save location, backup, and commit logic
├── inventory/     # Item reader (ItemRecord) and writer
├── editors/       # Stat and skill service layer (no UI — testable, GUI-ready)
├── crc.py         # CRC32C (Castagnoli) — RocksDB checksums
├── game_data.py   # Talent names, descriptions, stat names
├── process.py     # Game process detection and shutdown
└── cli.py         # Interactive menu shell (thin wrapper over service layer)
```

The `editors/` package is intentionally UI-free — `get_stats`/`set_stat_level` and `get_skills`/`set_skill_level` are pure service functions callable from both the CLI and any future GUI.

---
## License

This project is provided as-is for personal use. See the [Nexus Mods page](https://www.nexusmods.com/windrose/mods/153?tab=posts) for terms of use and redistribution details.