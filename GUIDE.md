# Windrose Save Editor — Full User Guide

## Table of Contents
1. [Before You Begin](#before-you-begin)
2. [Requirements](#requirements)
3. [Finding Your Save Folder](#finding-your-save-folder)
4. [Running the Editor](#running-the-editor)
5. [Main Menu Overview](#main-menu-overview)
6. [Feature Guides](#feature-guides)
   - [View Inventory](#1-view-inventory)
   - [Set Item Level](#2-set-item-level)
   - [Set Item Count](#3-set-item-count)
   - [Add Item](#4-add-item)
   - [Replace Item](#5-replace-item)
   - [Stat Editor](#6-stat-editor)
   - [Skill Editor](#7-skill-editor)
   - [Export Save as JSON](#e-export-save-as-json)
   - [Force-Close Game](#f-force-close-game)
   - [Save Changes](#s-save-changes)
   - [Restore a Backup](#r-restore-a-backup)
7. [Tips & Common Mistakes](#tips--common-mistakes)
8. [Troubleshooting](#troubleshooting)

---

## Before You Begin

> **⚠ ALWAYS BACK UP YOUR SAVE BEFORE EDITING.**
> The editor creates an automatic backup the first time you save changes in a session, but creating your own manual backup beforehand is strongly recommended.

Your save folder is located at:
```
%LOCALAPPDATA%\R5\Saved\SaveProfiles\<SteamID>\RocksDB\0.10.0\Players\<CharacterGUID>\
```

The editor reads a RocksDB database that Windrose uses to store all character data. It handles the low-level binary format automatically, but it is working directly on your save file, so care is required.

---

## Requirements

- **Python 3.10 or newer** — [Download here](https://www.python.org/downloads/)
- **psutil** (optional but recommended) — Enables auto-detection of the game process and force-close functionality.
  ```
  pip install psutil
  ```

No other third-party libraries are required. The editor uses only Python's standard library for all core functionality.

---

## Finding Your Save Folder

The editor can find your save automatically if you just run it with no arguments — it will search the default Windows save location and present you with a list of characters to choose from.

If auto-detection fails, you can pass the path manually:
```
python Windrose_Save_Editor.py "C:\Users\YourName\AppData\Local\R5\Saved\SaveProfiles\<SteamID>\RocksDB\0.10.0\Players\<CharacterGUID>"
```

You can also point it at a parent folder and it will search downward to find the correct player directory automatically.

---

## Running the Editor

### Auto-detect (recommended)
Simply double-click the script, or run it in a terminal with no arguments:
```
python Windrose_Save_Editor.py
```

If you have multiple Steam accounts or characters, you will be prompted to select one.

### Manual path
```
python Windrose_Save_Editor.py <path to save folder>
```

Once loaded, the editor will print your character's name, GUID, and save version, then drop you into the main menu.

---

## Main Menu Overview

```
══════════════════════════════════════════════════════════════════════
  WINDROSE SAVE EDITOR - Version 1.1b
══════════════════════════════════════════════════════════════════════
  Player: YourName  |  Save: <CharacterGUID>
  1. View inventory
  2. Set Item Level
  3. Set Item Count
  4. Add Item (Now Working!)
  5. Replace Item
  6. Stat Editor
  7. Skill Editor

  E. Export save as JSON (For inspection)
  F. Force-close game
  S. Save changes
  R. Restore a backup
  Q. Quit (unsaved changes will be lost)

  DEV. Experimental (Do not use)
```

Type the letter or number for your chosen option and press Enter.

---

## Feature Guides

### 1. View Inventory

Displays a table of every item currently in your inventory across all modules, showing:

| Column  | Description                                      |
|---------|--------------------------------------------------|
| #       | Row number used to select items in other menus   |
| Module  | The inventory module the item lives in           |
| Slot    | The slot index within that module                |
| Lvl     | Current level / max level (shown as `X/Y`)       |
| Cnt     | Stack count (blank if 1)                         |
| Item    | Internal item name                               |

No changes are made by this option. Press Enter to return to the menu.

---

### 2. Set Item Level

Lets you change the level of any equippable item (weapons, armour).

1. The inventory is printed automatically.
2. Enter the **#** of the item you want to change.
3. Enter the new level. The editor will show you the current and maximum level.

> Items that have no level attribute (consumables, stackables) cannot be edited here and will display `—` in the Lvl column.

---

### 3. Set Item Count

Changes the stack count of any item.

1. The inventory is printed automatically.
2. Enter the **#** of the item.
3. Enter the new count.

> Setting count on equipment (weapons/armour) is technically possible but has no in-game meaning — count is only relevant for stackable consumables and materials.

---

### 4. Add Item

Adds a brand-new item into an empty inventory slot.

1. Enter the full **ItemParams path** of the item you want to add. (These can be found using the included Item ID Database.html)
   - Example: `/R5BusinessRules/InventoryItems/Equipments/Armor/DA_EID_Armor_Flibustier_Base_Torso.DA_EID_Armor_Flibustier_Base_Torso`
   - These paths can be found in community item ID lists or by exporting your save as JSON (option E) and inspecting existing items.
2. The editor shows a table of all inventory modules and how many free slots each one has.
3. Enter the **module index** to add to (press Enter for module 0, which is the main bag).
4. Enter the **level** (1–15 for equipment, 0 for non-equipment).
5. Enter the **count** (1 for weapons/armour, more for stackables).

The editor will automatically find the first empty slot in the chosen module and place the item there. It also registers the item in the game's internal `WasTouchedItems` list so the game recognises it correctly.

**Tips on ItemParams paths:**
- The path must start with `/R5BusinessRules/`
- Do not include `/Plugins/` or `/Content/` — the editor strips these automatically if you accidentally paste them. (And they are auto parsed in the DB)
- The path must end with `.<AssetName>` (the asset name repeated after the dot).

---

### 5. Replace Item

Swaps the type of an existing item while keeping it in the same slot. Useful for changing a weapon or armour piece to a different variant (e.g. a green-quality rapier to a blue-quality rapier).

1. The inventory is printed automatically.
2. Enter the **#** of the item to replace.
3. Enter the new **ItemParams path**.
4. If both the old and new item are equipment, you will be prompted to set a new level (press Enter to keep the existing one).

The editor automatically:
- Generates a fresh Item ID for the new item.
- Enforces equipment rules (weapons/armour get a minimum level of 1; consumables have their level reset to 0).
- Offers to set a quantity if you are replacing equipment with a stackable.

---

### 6. Stat Editor

Edits your six core character stats (Strength, Agility, Precision, Mastery, Vitality, Endurance). Each stat has a level between 0 and its maximum (usually 60).

1. A numbered list of all stats and their current levels is shown.
2. Enter the **number** of the stat to edit.
3. Enter the new level (capped automatically at the stat's maximum).

**ProgressionPoints** (the total used to track unlock thresholds) is recalculated automatically after every change.

---

### 7. Skill Editor

Edits your talent tree (skills). Skills are organised into four categories:

| # | Category | Direction |
|---|----------|-----------|
| 1 | Fencer   | UP        |
| 2 | Toughguy | LEFT      |
| 3 | Marksman | DOWN      |
| 4 | Crusher  | RIGHT     |

Each skill has a level of 0–3. A level of 0 means the skill is not unlocked.

1. Select a **category**.
2. A table of all skills in that category is shown, with current levels.
3. Press **D** to toggle descriptions on/off for each skill.
4. Enter the **number** of the skill to edit, then enter the new level.

If a skill doesn't yet exist in your save (because you've never unlocked it), the editor will create it automatically with the correct internal structure when you set it to level 1 or higher.

**ProgressionPoints** for the talent tree is updated automatically after each change.

---

### E. Export Save as JSON

Exports the entire save document to a human-readable JSON file placed next to your save folder. This is useful for:
- Inspecting item paths to use with Add Item or Replace Item
- Debugging unexpected editor behaviour
- Sharing save data for community inspection

No changes are made to the save by this option.

---

### F. Force-Close Game

If you have **psutil** installed, this option will immediately terminate any running Windrose process. This is a hard kill — equivalent to ending the task in Task Manager.

> **Note:** Use this only if the game is frozen or you cannot access the in-game quit menu. The editor's Save option will prompt you to quit the game normally (via the in-game menu) before writing changes, which is the preferred and safest method.

---

### S. Save Changes

Writes all pending changes back to the save database.

1. A summary of all changes made in this session is displayed.
2. Confirm with **Y** (or press Enter).
3. If this is the first save of the session, a **full automatic backup** of your entire save root (Accounts + Players + Worlds) is created before any changes are written.
4. If the game is still running, the editor will prompt you to quit via the in-game menu and wait until it detects the process has closed before writing. This is important — a clean exit ensures RocksDB flushes all data safely.
5. The modified data is written directly via the RocksDB C API into a new WAL log file.
6. The WAL is verified by reading it back before the save is considered complete.

> **Do not force-quit the game before saving** unless necessary. Always use Esc → Quit in-game to ensure a clean database close.

---

### R. Restore a Backup

Lists all available backups (newest first) and lets you roll back to one.

- Full backups (labelled `[full]`) cover the entire Steam save root including Accounts, Players, and Worlds databases.
- Older partial backups (labelled `[players only]`) cover only the player character database.

After restoring, the editor exits and asks you to relaunch after verifying the game loads correctly.

---

## Tips & Common Mistakes

**Always make sure the game is closed before running the script.** writing to an open database can and WILL cause corruption or infinite loading screens.

**Don't use Add Item if the module is full.** The editor will warn you and refuse to add the item. Either free up a slot first by removing an item (DEV menu), or target a different module.

**ItemParams paths are case-sensitive.** Copy them exactly from the Database or a community reference. A mistyped path will result in a corrupted save.

**You can make multiple changes before saving.** All edits are held in memory and only written when you press S. This lets you make several changes and review them before committing.

**The DEV menu contains experimental options that are unsupported.** Features under development or that need further testing will be located here. Use with caution, support will NOT be provided.

---

## Troubleshooting

**"No .log file found in save folder"**
You have pointed the editor at the wrong folder. Make sure the folder you specify contains files named `CURRENT`, `MANIFEST-*`, `*.sst`, and `*.log`. Use the auto-detect mode if you are unsure.

**"WAL is empty — data has been compacted into SST files"**
This is normal after the game has been run and closed cleanly several times. The editor will attempt to read the data from the SST files using librocksdb. If this fails, see the message about `rocksdb.dll` below.

**"rocksdb.dll not found"**
The editor needs the RocksDB native library to read SST files. This is included. If you would like to download `rocksdb.dll` manually it can be found in the [RocksDB NuGet package](https://www.nuget.org/packages/RocksDB) (open the `.nupkg` as a ZIP, grab `runtimes/win-x64/native/rocksdb.dll`) and place it in the same folder as the script.

**Infinite loading screen after saving**
Restore your backup immediately. This usually means the game was not cleanly closed before the save was written, or a WAL file conflict occurred. Always quit via the in-game menu before running the script.
