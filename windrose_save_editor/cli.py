from __future__ import annotations

"""
Windrose Save Editor — interactive CLI.

Usage:
    python -m windrose_save_editor <save_directory>

The save_directory should contain: CURRENT, MANIFEST-*, *.sst, *.log
Typically: %LOCALAPPDATA%\\R5\\Saved\\SaveProfiles\\<character_folder>

ALWAYS back up your save folder before editing!
"""

import json
import sys
from datetime import datetime
from pathlib import Path

from windrose_save_editor.bson.parser import parse_bson
from windrose_save_editor.bson.types import BSONArray, BSONDoc
from windrose_save_editor.editors import (
    StatEntry,
    get_stats,
    set_stat_level,
    SkillEntry,
    get_skills,
    set_skill_level,
)
from windrose_save_editor.game_data import SKILL_CATEGORIES, TALENT_DESCS
from windrose_save_editor.inventory import (
    ItemRecord,
    get_all_items,
    get_empty_slots,
    get_module_capacity,
    slot_has_item,
    blank_item,
    blank_slot_with_item,
    new_item_guid,
)
from windrose_save_editor.process import kill_game
from windrose_save_editor.rocksdb import read_wal, scan_sst_for_player
from windrose_save_editor.save import (
    SaveSession,
    commit_changes,
    find_accounts,
    find_player_dirs,
    find_profiles_root,
    find_wal,
    peek_player_name,
    resolve_save_dir,
    restore_backup,
    save_backup,
)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _print_header(session: SaveSession) -> None:
    print("\n" + "=" * 70)
    print("  WINDROSE SAVE EDITOR - Version 1.1b")
    print("=" * 70)
    print(f"  Player: {session.doc.get('PlayerName', '?')}  |  Save: {session.save_dir.name}")


def _print_inventory(items: list[ItemRecord]) -> None:
    print(f"\n{'#':<4} {'Module':<8} {'Slot':<6} {'Lvl':<6} {'Cnt':<5} Item")
    print("-" * 70)
    for i, it in enumerate(items):
        lvl = f"{it['level']}/{it['max_level']}" if it['level'] is not None else "-"
        cnt = it['count'] if it['count'] > 1 else ""
        name = it['item_name']
        if len(name) > 45:
            name = name[:43] + "..."
        print(f"{i:<4} {it['module']:<8} {it['slot']:<6} {lvl:<6} {str(cnt):<5} {name}")


def _fix_item_params(params: str) -> str:
    """Normalise a copy-pasted ItemParams path.

    - Prepends '/' if missing.
    - Strips a leading '/Plugins/' segment (old HTML guide format).
    - Replaces '/Content/' with '/' (Unreal content-path shorthand).
    """
    if not params:
        return params
    if not params.startswith('/'):
        params = '/' + params
    if params.startswith('/Plugins/'):
        params = params[len('/Plugins/'):]
    params = params.replace('/Content/', '/')
    return params


# ---------------------------------------------------------------------------
# Stat editor
# ---------------------------------------------------------------------------

def _run_stat_editor(session: SaveSession) -> tuple[bool, str | None]:
    """Interactive stat editor. Returns (changed, changelog_entry)."""
    print("\n  === STAT EDITOR ===")
    print()

    stats = get_stats(session.doc)
    for i, entry in enumerate(stats, 1):
        print(f"  {i}. {entry.name:<14}  {entry.level}/{entry.max_level}")

    print()
    choice = input("  Stat # to edit (or Enter to go back): ").strip()
    if not choice:
        return False, None

    try:
        idx = int(choice) - 1
        stat = stats[idx]
    except (ValueError, IndexError):
        print("  Invalid choice.")
        input("  Press Enter..."); return False, None

    try:
        new_lvl = int(input(
            f"  New level for {stat.name} (current: {stat.level}, max: {stat.max_level}): "
        ))
    except ValueError:
        print("  Invalid level.")
        input("  Press Enter..."); return False, None

    old_lvl = stat.level
    set_stat_level(session.doc, stat.node_key, new_lvl)
    # Reflect clamped value back for the success message
    clamped = max(0, min(new_lvl, stat.max_level))
    print(f"  -> {stat.name} -> {clamped}/{stat.max_level}")
    return True, f"Stat: {stat.name} {old_lvl} -> {clamped}"


# ---------------------------------------------------------------------------
# Skill editor
# ---------------------------------------------------------------------------

def _create_skill_node(
    doc: BSONDoc,
    entry: SkillEntry,
    new_lvl: int,
) -> str:
    """Insert a new TalentTree node for a skill not yet present in the save.

    Returns the new node_key string.
    """
    from windrose_save_editor.inventory.reader import get_progression

    pp = get_progression(doc)
    tt = pp.get('TalentTree', {})
    nodes = tt.get('Nodes', {})

    new_k = str(max((int(x) for x in nodes.keys()), default=-1) + 1)
    category = entry.category
    # Derive suffix from the _talent_key: "Talent_<Cat>_<Suffix>" -> "<Suffix>"
    suffix = entry._talent_key.replace(f"Talent_{category}_", "", 1)
    da = f"DA_Talent_{category}_{suffix}"

    # Look up UISlotTag from the editors module's internal data (re-derive it)
    # We reconstruct from what SkillEntry carries; UISlotTag is not stored there,
    # so we replicate the same logic the monolith used.
    from windrose_save_editor.editors.skills import _TALENT_NODE_DATA  # type: ignore[attr-defined]
    meta = _TALENT_NODE_DATA.get(da, {})
    ui_tag = meta.get('UISlotTag', '')
    node_key_tag = f"Talent.Tree.{category}.{suffix}"
    perk_path = entry._perk_path

    perks_arr: BSONArray = BSONArray({'0': perk_path})
    reqs_arr: BSONArray = BSONArray({})

    new_node: dict = {
        'ActivePerk': perk_path if new_lvl > 0 else '',
        'NodeData': {
            'MaxNodeLevel': entry.max_level,
            'NodePointsCost': 1,
            'Perks': perks_arr,
            'Requirements': {
                'RequiredPointsByNodeTag': reqs_arr,
                'SearchPolicy': 'All',
            },
            'UISlotTag': {'TagName': ui_tag},
        },
        'NodeKey': {'TagName': node_key_tag},
        'NodeLevel': new_lvl,
    }
    nodes[new_k] = new_node
    print(f"  [Auto] Created new node {new_k} for {entry.name}")
    return new_k


def _run_skill_editor(session: SaveSession) -> tuple[bool, str | None]:
    """Interactive skill editor with category sub-menu."""
    cats = list(SKILL_CATEGORIES.items())

    while True:
        print("\n  === SKILL EDITOR ===")
        print()
        for i, (cat_key, cat_info) in enumerate(cats, 1):
            print(f"  {i}. {cat_info['label']}")
        print("  B. Back")
        print()

        cat_choice = input("  Category: ").strip().lower()
        if cat_choice == 'b':
            return False, None

        try:
            cat_key, cat_info = cats[int(cat_choice) - 1]
        except (ValueError, IndexError):
            print("  Invalid choice.")
            continue

        skills_by_cat = get_skills(session.doc)
        entries: list[SkillEntry] = skills_by_cat.get(cat_key, [])

        if not entries:
            print(f"  No {cat_key} skills found (may not be unlocked yet).")
            input("  Press Enter..."); continue

        show_descs = False
        while True:
            print(f"\n  {cat_info['label']} Skills")
            print(f"  {'#':<4} {'Name':<30} {'Level'}")
            print("  " + "-" * 45)
            for i, entry in enumerate(entries, 1):
                print(f"  {i:<4} {entry.name:<30} {entry.level}/{entry.max_level}")
                if show_descs and entry.description:
                    print(f"       {entry.description}")

            print()
            print("  D. Toggle descriptions  |  B. Back to categories")
            print()
            skill_choice = input("  Skill # to edit: ").strip().lower()

            if skill_choice == 'b':
                break
            if skill_choice == 'd':
                show_descs = not show_descs
                continue

            try:
                si = int(skill_choice) - 1
                entry = entries[si]
            except (ValueError, IndexError):
                print("  Invalid choice.")
                continue

            try:
                new_lvl = int(input(
                    f"  New level for {entry.name} (current: {entry.level}, max: {entry.max_level}): "
                ))
            except ValueError:
                print("  Invalid level.")
                continue

            old_lvl = entry.level

            if not entry.node_key:
                # Node not yet in save — create it
                node_key = _create_skill_node(session.doc, entry, new_lvl)
                # After creation set_skill_level can address the node normally
                set_skill_level(session.doc, node_key, new_lvl)
                # Re-fetch to get fresh entries with updated node keys
                skills_by_cat = get_skills(session.doc)
                entries = skills_by_cat.get(cat_key, [])
            else:
                set_skill_level(session.doc, entry.node_key, new_lvl)
                # Refresh local list
                skills_by_cat = get_skills(session.doc)
                entries = skills_by_cat.get(cat_key, [])

            clamped = max(0, min(new_lvl, entry.max_level))
            print(f"  -> {entry.name} -> {clamped}/{entry.max_level}")
            return True, f"Skill: {entry.name} {old_lvl} -> {clamped}"

    return False, None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


_USAGE = (
    "Windrose Save Editor\n"
    "\n"
    "Usage:\n"
    "  python -m windrose_save_editor                  # auto-detect save\n"
    "  python -m windrose_save_editor <save_directory> # explicit path\n"
    "\n"
    "The save_directory should contain: CURRENT, MANIFEST-*, *.sst, *.log\n"
    "Typically: %LOCALAPPDATA%\\R5\\Saved\\SaveProfiles\\<character_folder>\n"
)


def pick_save_interactively() -> Path | None:
    profiles_root = find_profiles_root()
    if not profiles_root:
        print("[ERROR] Could not find save profiles folder automatically.")
        print("  Run with a path argument:")
        print("    Windrose Save Editor.exe <path to Players/GUID folder>")
        return None

    accounts = find_accounts(profiles_root)
    if not accounts:
        print(f"[ERROR] No Steam or Epic account folders found in {profiles_root}")
        return None

    if len(accounts) == 1:
        account_dir, acct_type = accounts[0]
        print(f"  {acct_type} account: {account_dir.name}")
    else:
        print("\n  Accounts found:")
        for i, (d, acct_type) in enumerate(accounts, 1):
            print(f"    {i}. [{acct_type}] {d.name}")
        print()
        try:
            choice = int(input("  Select account: ")) - 1
            account_dir, acct_type = accounts[choice]
        except (ValueError, IndexError):
            print("  Cancelled.")
            return None

    player_dirs = find_player_dirs(account_dir)
    if not player_dirs:
        print(f"[ERROR] No player saves found in {account_dir}")
        return None

    if len(player_dirs) == 1:
        return player_dirs[0]

    print("\n  Characters found:")
    entries: list[tuple[Path, str]] = []
    for d in player_dirs:
        print(f"    Loading {d.name}...", end="\r", flush=True)
        name = peek_player_name(d)
        entries.append((d, name))
        label = f"{d.name}  |  {name}" if name else d.name
        print(f"    {len(entries)}. {label}          ")

    print()
    try:
        choice = int(input("  Select character: ")) - 1
        return entries[choice][0]
    except (ValueError, IndexError):
        print("  Cancelled.")
        return None


def main() -> None:  # noqa: C901 — intentionally long menu dispatch
    if len(sys.argv) >= 2:
        save_dir = Path(sys.argv[1]).resolve()
        if not save_dir.exists():
            print(f"[ERROR] Directory not found: {save_dir}")
            sys.exit(1)
        save_dir = resolve_save_dir(save_dir)
    else:
        save_dir = pick_save_interactively()
        if save_dir is None:
            sys.exit(0)

    if not (save_dir / 'CURRENT').exists():
        print("[ERROR] Could not find a save folder (no CURRENT file) under:")
        print(f"        {Path(sys.argv[1]).resolve()}")
        print(f"\n  Run:  dir \"{Path(sys.argv[1]).resolve()}\"  to see what's inside.")
        sys.exit(1)

    wal_path = find_wal(save_dir)
    print(f"\nReading: {wal_path.name}")

    result = read_wal(wal_path)
    cf_id = 2
    player_key: bytes | None = None

    if result is not None:
        seq = result.sequence
        cf_id = result.cf_id
        player_key = result.player_key
        bson_bytes = result.bson_bytes
        batch_count = result.batch_count

        # Warn if game appears to be running
        try:
            import psutil as _psutil
            game_running = any(
                p.info['name'] in ('R5.exe', 'Windrose.exe', 'R5-Win64-Shipping.exe')
                for p in _psutil.process_iter(['name'])
                if p.info.get('name')
            )
        except Exception:
            game_running = False

        if game_running:
            print()
            print("  WARNING  Game is RUNNING - player data read from live WAL.")
            print()
            print("  Make your edits, then use option 9 to save.")
            print("  The editor will guide you through closing the game safely.")
            print()
    else:
        print("  WAL is empty - data has been compacted into SST files.")
        print("  Scanning SST files for player data...")
        sst_result = scan_sst_for_player(save_dir)
        if sst_result is None:
            print("[ERROR] Could not find player data in WAL or SST files.")
            sys.exit(1)
        player_key, bson_bytes = sst_result
        seq = 99999
        batch_count = 1

    assert player_key is not None  # guaranteed by branches above

    doc: BSONDoc = parse_bson(bson_bytes)

    print(f"Player:   {doc.get('PlayerName', '?')}")
    print(f"GUID:     {doc.get('_guid', '?')}")
    print(f"Version:  {doc.get('_version', '?')}")
    print(f"WAL seq:  {seq}")

    session = SaveSession(
        save_dir=save_dir,
        wal_path=wal_path,
        player_key=player_key,
        doc=doc,
        original_bson=bson_bytes,
        seq=seq,
        cf_id=cf_id,
        batch_count=batch_count,
        modified=False,
        backed_up=False,
    )

    changelog: list[str] = []

    while True:
        _print_header(session)
        print("  1. View inventory")
        print("  2. Set Item Level")
        print("  3. Set Item Count")
        print("  4. Add Item (Now Working!)")
        print("  5. Replace Item")
        print("  6. Stat Editor")
        print("  7. Skill Editor")
        print("")
        print("  E. Export save as JSON (For inspection)")
        print("  F. Force-close game")
        print("  S. Save changes")
        print("  R. Restore a backup")
        print("  Q. Quit (unsaved changes will be lost)")
        print("")
        print("  DEV. Experimental (Do not use)")
        print()

        raw = input("  Choice: ").strip().lower()

        # Resolve aliased choices before dispatch
        choice = raw
        if choice == '4':
            choice = '_add'
        elif choice == 'dev':
            print("\n  WARNING  EXPERIMENTAL - Use at your own risk (support WILL NOT be provided)")
            print("  1. Remove item from inventory")
            print("  B. Back")
            print()
            dev_choice = input("  Choice: ").strip().lower()
            if dev_choice == '1':
                choice = '_remove'
            else:
                input("  Press Enter..."); continue

        # ------------------------------------------------------------------
        # Option 1 — View inventory
        # ------------------------------------------------------------------
        if choice == '1':
            items = get_all_items(session.doc)
            if not items:
                print("  No items found in inventory.")
            else:
                _print_inventory(items)
            input("\n  Press Enter to continue...")

        # ------------------------------------------------------------------
        # Option 2 — Set item level
        # ------------------------------------------------------------------
        elif choice == '2':
            items = get_all_items(session.doc)
            _print_inventory(items)
            try:
                idx = int(input("\n  Item # to change level: "))
                it = items[idx]
                if it['level'] is None:
                    print(f"  '{it['item_name']}' has no level attribute.")
                    input("  Press Enter..."); continue
                new_lvl = int(input(f"  New level (current: {it['level']}, max: {it['max_level']}): "))
                attrs = it['attrs_ref']
                for a in attrs.values():
                    if isinstance(a, dict) and 'Level' in a.get('Tag', {}).get('TagName', ''):
                        a['Value'] = new_lvl
                        break
                print(f"  -> {it['item_name']} -> level {new_lvl}")
                changelog.append(f"Level:   {it['item_name']} {it['level']} -> {new_lvl}")
                session.modified = True
            except (ValueError, IndexError) as e:
                print(f"  Invalid input: {e}")
            input("  Press Enter...")

        # ------------------------------------------------------------------
        # Option 3 — Set item count
        # ------------------------------------------------------------------
        elif choice == '3':
            items = get_all_items(session.doc)
            _print_inventory(items)
            try:
                idx = int(input("\n  Item # to change count: "))
                it = items[idx]
                new_cnt = int(input(f"  New count (current: {it['count']}): "))
                it['stack_ref']['Count'] = new_cnt
                print(f"  -> {it['item_name']} -> count {new_cnt}")
                changelog.append(f"Count:   {it['item_name']} {it['count']} -> {new_cnt}")
                session.modified = True
            except (ValueError, IndexError) as e:
                print(f"  Invalid input: {e}")
            input("  Press Enter...")

        # ------------------------------------------------------------------
        # Option 5 — Replace item
        # ------------------------------------------------------------------
        elif choice == '5':
            items = get_all_items(session.doc)
            _print_inventory(items)
            print()
            print("  Replace an item by swapping its ItemParams.")
            print("  The slot, level, count and slot structure stay identical.")
            print("  Example: replace Green Rapier with Blue/Purple variant.")
            print()
            try:
                idx = int(input("  Item # to replace: "))
                it = items[idx]
            except (ValueError, IndexError):
                print("  Invalid item number.")
                input("  Press Enter..."); continue

            print(f"  Current: {it['item_name']}")
            print(f"  Current ItemParams: {it['item_params']}")
            print()
            raw_params = input("  New ItemParams: ").strip()
            if not raw_params:
                print("  Cancelled.")
                input("  Press Enter..."); continue

            new_params = _fix_item_params(raw_params)

            # Update ItemParams and generate a fresh ItemId
            it['item_ref']['ItemParams'] = new_params
            it['item_ref']['ItemId'] = new_item_guid()

            # Determine equipment status using same prefixes as the inventory module
            _WEAPON_PREFIXES = ('DA_EID_MeleeWeapon_', 'DA_EID_RangeWeapon_', 'DA_EID_Weapon_')
            _ARMOR_PREFIXES = (
                'DA_EID_Armor_', 'DA_EID_Helmet_', 'DA_EID_Gloves_',
                'DA_EID_Boots_', 'DA_EID_Legs_', 'DA_EID_Chest_',
            )
            _EQUIP_PREFIXES = _WEAPON_PREFIXES + _ARMOR_PREFIXES

            def _is_equip(p: str) -> bool:
                name = p.split('/')[-1].split('.')[0]
                return any(name.startswith(pfx) for pfx in _EQUIP_PREFIXES)

            old_is_equip = _is_equip(it['item_params'])
            new_is_equip = _is_equip(new_params)

            # Only prompt for level when both old and new are equipment
            if new_is_equip and old_is_equip:
                new_level_str = input(
                    f"  New level (Enter to keep {it['level']}): "
                ).strip()
                if new_level_str:
                    try:
                        new_level = int(new_level_str)
                        for a in it['attrs_ref'].values():
                            if isinstance(a, dict) and 'Level' in a.get('Tag', {}).get('TagName', ''):
                                a['Value'] = new_level
                                break
                    except ValueError:
                        pass

            # Enforce equipment integrity rules
            if new_is_equip:
                it['stack_ref']['Count'] = 1
                attrs = it['item_ref'].get('Attributes', {})
                level_attr = None
                for a in attrs.values():
                    if isinstance(a, dict) and 'Level' in a.get('Tag', {}).get('TagName', ''):
                        level_attr = a
                        break
                if level_attr is None:
                    it['item_ref'].setdefault('Attributes', {})['0'] = {
                        'MaxValue': 15,
                        'Tag': {'TagName': 'Inventory.Item.Attribute.Level'},
                        'Value': 1,
                    }
                    print("  [Auto] Added missing level attribute (set to 1)")
                elif level_attr.get('Value', 0) < 1:
                    level_attr['Value'] = 1
                    print("  [Auto] Level was 0 - set to 1 (minimum for equipment)")
            elif old_is_equip and not new_is_equip:
                attrs = it['item_ref'].get('Attributes', {})
                for a in attrs.values():
                    if isinstance(a, dict) and 'Level' in a.get('Tag', {}).get('TagName', ''):
                        a['Value'] = 0
                        print("  [Auto] Level reset to 0 (non-equipment item)")
                        break

            # If going from equipment -> stackable, offer to set quantity
            if old_is_equip and not new_is_equip:
                qty_str = input("  Set quantity (Enter to keep 1): ").strip()
                if qty_str:
                    try:
                        qty = max(1, int(qty_str))
                        it['stack_ref']['Count'] = qty
                    except ValueError:
                        pass

            new_name = new_params.split('/')[-1].split('.')[0]
            print(f"  -> Replaced with: {new_name}")
            changelog.append(f"Replace: {it['item_name']} -> {new_name}")
            session.modified = True
            input("  Press Enter...")

        # ------------------------------------------------------------------
        # Option 6 — Stat editor
        # ------------------------------------------------------------------
        elif choice == '6':
            changed, msg = _run_stat_editor(session)
            if changed:
                session.modified = True
                if msg:
                    changelog.append(msg)
            input("  Press Enter...")

        # ------------------------------------------------------------------
        # Option 7 — Skill editor
        # ------------------------------------------------------------------
        elif choice == '7':
            changed, msg = _run_skill_editor(session)
            if changed:
                session.modified = True
                if msg:
                    changelog.append(msg)

        # ------------------------------------------------------------------
        # Option E — Export JSON
        # ------------------------------------------------------------------
        elif choice == 'e':
            out = session.save_dir.parent / (
                f"{session.save_dir.name}_dump_{datetime.now().strftime('%H%M%S')}.json"
            )
            with open(out, 'w', encoding='utf-8') as f:
                json.dump(session.doc, f, indent=2, ensure_ascii=False, default=str)
            print(f"  -> Exported: {out}")
            input("  Press Enter...")

        # ------------------------------------------------------------------
        # Option F — Force-close game
        # ------------------------------------------------------------------
        elif choice == 'f':
            kill_game()
            input("  Press Enter...")

        # ------------------------------------------------------------------
        # Option 9 / S — Save changes
        # ------------------------------------------------------------------
        elif choice in ('9', 's'):
            if not session.modified:
                print("  No changes to save.")
                input("  Press Enter..."); continue

            print()
            print("  Changes this session:")
            print("  " + "-" * 60)
            for entry in changelog:
                print(f"    {entry}")
            if not changelog:
                print("    (no tracked changes)")
            print("  " + "-" * 60)
            print()
            confirm_save = input("  Save these changes? [Y/n]: ").strip().lower()
            if confirm_save not in ('', 'y', 'yes'):
                print("  Save cancelled.")
                input("  Press Enter..."); continue

            if not session.backed_up:
                print()
                save_backup(session.save_dir)
                session.backed_up = True

            try:
                ok = commit_changes(session)
                if ok:
                    session.modified = False
                    print("  -> Changes written. Launch the game to verify.")
            except Exception as e:
                import traceback
                print(f"  [ERROR] Save failed: {e}")
                traceback.print_exc()
            input("  Press Enter...")

        # ------------------------------------------------------------------
        # Option A / R — Restore backup
        # ------------------------------------------------------------------
        elif choice in ('a', 'r'):
            confirm = input("  Replace current save with a backup? [y/N]: ").strip().lower()
            if confirm == 'y':
                if restore_backup(session.save_dir):
                    print("  Exiting - relaunch editor after verifying.")
                    break
            input("  Press Enter...")

        # ------------------------------------------------------------------
        # DEV: Add item
        # ------------------------------------------------------------------
        elif choice == '_add':
            print("\n  Enter the ItemParams path for the item to add.")
            print("  Example: /R5BusinessRules/InventoryItems/Equipments/Armor/DA_EID_Armor_Flibustier_Base_Torso.DA_EID_Armor_Flibustier_Base_Torso")
            print("  (This is shown in the Item ID Guide when you click an item)")
            print()
            raw_params = input("  ItemParams: ").strip()
            if not raw_params:
                input("  Cancelled. Press Enter..."); continue

            params = _fix_item_params(raw_params)

            # Show module capacities to help the user pick
            mods = session.doc.get('Inventory', {}).get('Modules', {})
            print()
            print("  Module     Used / Capacity   Free slots")
            for m_idx in sorted(mods.keys(), key=lambda x: int(x)):
                m = mods[m_idx]
                slots = m.get('Slots', {})
                cap = get_module_capacity(m)
                used = sum(1 for s in slots.values() if slot_has_item(s))
                free = cap - used
                free_str = f"ok {free} free" if free > 0 else "- full"
                print(f"    {m_idx:<10} {used:>4} / {cap:<6}   {free_str}")
            print()

            try:
                mod_raw = input("  Module index [0]: ").strip()
                mod_idx = int(mod_raw) if mod_raw else 0
                level = int(input("  Level (1-15, or 0 if not applicable): "))
                count = int(input("  Count (1 for equipment, more for stackables): "))
            except ValueError:
                print("  Invalid input.")
                input("  Press Enter..."); continue

            empty = get_empty_slots(session.doc, mod_idx)
            mods = session.doc['Inventory']['Modules']
            if not empty:
                mod_obj = mods.get(str(mod_idx), {})
                cap = get_module_capacity(mod_obj)
                print(f"  Module {mod_idx} is full ({cap}/{cap}).")
                print("  Pick a different module or remove an item first.")
                input("  Press Enter..."); continue

            if str(mod_idx) not in mods:
                print(f"  Module {mod_idx} not found.")
                input("  Press Enter..."); continue

            slot_idx = empty[0]
            slots = mods[str(mod_idx)].setdefault('Slots', {})
            existing = slots.get(str(slot_idx))
            new_item = blank_item(params, level)
            if existing is not None:
                stack = existing.setdefault('ItemsStack', {})
                stack['Count'] = count
                stack['Item'] = new_item
                existing['SlotId'] = slot_idx
            else:
                slots[str(slot_idx)] = blank_slot_with_item(
                    params, level, count, slot_idx, mod=mods[str(mod_idx)]
                )

            # Register in WasTouchedItems so the game recognises the item instance
            inv_meta = session.doc.setdefault('PlayerMetadata', {}).setdefault('InventoryMetadata', {})
            touched = inv_meta.setdefault('WasTouchedItems', {})
            existing_keys = [int(k) for k in touched.keys() if str(k).lstrip('-').isdigit()]
            next_key = str(max(existing_keys, default=-1) + 1)
            touched[next_key] = {
                'Item': {
                    'Attributes': new_item.get('Attributes', BSONArray()),
                    'Effects': BSONArray(),
                    'ItemId': new_item['ItemId'],
                    'ItemParams': params,
                },
                'bIsNew': False,
            }

            name = params.split('/')[-1].split('.')[0]
            print(f"  -> Added '{name}' to module {mod_idx} slot {slot_idx}")
            changelog.append(f"Add:     {name} -> module {mod_idx} slot {slot_idx}")
            session.modified = True
            input("  Press Enter...")

        # ------------------------------------------------------------------
        # DEV: Remove item
        # ------------------------------------------------------------------
        elif choice == '_remove':
            items = get_all_items(session.doc)
            _print_inventory(items)
            try:
                idx = int(input("\n  Item # to REMOVE: "))
                it = items[idx]
                confirm = input(f"  Remove '{it['item_name']}'? [y/N] ").strip().lower()
                if confirm == 'y':
                    mods = session.doc['Inventory']['Modules']
                    slots = mods[str(it['module'])]['Slots']
                    del slots[str(it['slot'])]
                    print(f"  -> Removed '{it['item_name']}'")
                    session.modified = True
            except (ValueError, IndexError) as e:
                print(f"  Invalid input: {e}")
            input("  Press Enter...")

        # ------------------------------------------------------------------
        # Option 0 / Q — Quit
        # ------------------------------------------------------------------
        elif choice in ('0', 'q'):
            if session.modified:
                confirm = input("  Unsaved changes will be lost. Quit anyway? [y/N] ").strip().lower()
                if confirm != 'y':
                    continue
            break

    print("\nBye!")
