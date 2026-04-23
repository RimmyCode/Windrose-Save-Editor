WINDROSE ITEM ID DATABASE & SAVE EDITOR
By Rimmy (KHBIN)
________________________________________

WHAT IS THIS?

Two community tools for Windrose:

Item ID Database — a searchable, filterable HTML guide of every item in the game.
Shows item names, categories, rarities, stats, and the ItemParams path needed for
the save editor. Open it in any browser, no install required.

Save Editor — a Python script that lets you edit your character save file directly.
Replace items in your inventory, change item levels, and view your inventory contents.

________________________________________

REQUIREMENTS

- Python 3.10 or newer
- rocksdb.dll (included)
- Install requirements.txt

________________________________________

HOW TO USE THE SAVE EDITOR

IMPORTANT: Close Windrose completely before running the editor.

1. Open a terminal and run:

   python Windrose_Save_Editor_v3.py "C:\Users\YOU\AppData\Local\R5\Saved\SaveProfiles\<SteamID>\RocksDB\0.10.0\Players\<GUID>"

2. To give yourself an item:

   - Have a sacrifice item already in your inventory in-game
     (a dodo egg, a coin, anything disposable -- it will be overwritten).

   - Find the item you want in the Item ID Database (item_guide.html),
     click it, and copy the ItemParams field from the popup window.

   - In the save editor, choose option 4 (Replace item).

   - Pick the sacrifice item from the list.

   - Paste the ItemParams you copied and set the level (1-15).

   - Choose option 7 (Save) when done.

3. Launch the game and check your inventory.

________________________________________

HOW TO USE THE ITEM ID DATABASE

Open item_guide.html in any browser. Use the filters at the top to search by
name, rarity, category, or stat. Click any item to see its full details including
the ItemParams path for use with the save editor.

________________________________________

REGENERATING THE ITEM ID DATABASE

If you want to generate a fresh guide from your own FModel export:

1. Export items from FModel into a folder.
2. Export Game.locres as JSON, rename it to game.json, place it in the export folder.
3. Run:

   python "parse_items Only Valid.py" "<your FModel export folder>" "./output"

________________________________________

NOTES

- The save editor creates a full backup of your save before writing any changes.
  If something goes wrong, use option A (Restore a backup) to roll back.

- Only replace items you already have in your inventory. Adding to empty slots
  may be rejected by the game's item validation.

- Tested on Windrose version 0.10.0. May need updates after major patches.

________________________________________

This is a community tool, not affiliated with the Windrose developers.