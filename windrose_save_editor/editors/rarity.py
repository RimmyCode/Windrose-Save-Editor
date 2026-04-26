from __future__ import annotations

"""Rarity upgrade logic — preview and apply item rarity upgrades.

Requires Item ID Database.html to be present next to the editor.
Use :func:`preview_upgrades` to build a list of proposed changes,
then :func:`apply_upgrades` to write them into the live document.
"""

from windrose_save_editor.bson.types import BSONDoc
from windrose_save_editor.game_data import RARITY_VALUE
from windrose_save_editor.inventory.reader import get_all_items
from windrose_save_editor.inventory.writer import ensure_equipment_integrity, new_item_guid
from windrose_save_editor.save.item_db import (
    build_db_indices,
    find_db_item,
    load_item_db,
    _family_key,
)


def _is_upgrade_safe(db_item: dict) -> bool:
    """Skip quest / invisible / NPC items from rarity upgrades."""
    item_type = str(db_item.get('item_type') or '')
    if item_type.startswith((
        'Inventory.ItemType.Quest',
        'Inventory.ItemType.Invisible',
        'Inventory.ItemType.NPC',
    )):
        return False
    return True


def find_best_upgrade(
    db_item: dict,
    by_family: dict[str, list[dict]],
    target_rarity: str = 'Highest Available',
) -> dict | None:
    """Return the best available rarity upgrade for *db_item*, or None."""
    current_rank = RARITY_VALUE.get(db_item.get('rarity', ''), 0)
    group = by_family.get(_family_key(db_item), [])
    if not group:
        return None

    if target_rarity and target_rarity != 'Highest Available':
        candidates = [it for it in group if it.get('rarity') == target_rarity]
    else:
        candidates = list(group)

    candidates = [
        it for it in candidates
        if RARITY_VALUE.get(it.get('rarity', ''), 0) > current_rank
    ]
    if not candidates:
        return None

    candidates.sort(
        key=lambda x: (RARITY_VALUE.get(x.get('rarity', ''), 0), int(x.get('max_level') or 0)),
        reverse=True,
    )
    return candidates[0]


def preview_upgrades(
    doc: BSONDoc,
    target_rarity: str = 'Highest Available',
    db_path=None,
) -> list[dict]:
    """Return a list of proposed rarity upgrades for the current save.

    Each entry is a dict:
        inv_item   : ItemRecord from get_all_items()
        db_item    : current DB entry (or None if unknown)
        upgrade    : proposed DB entry to upgrade to (or None if already at max / unknown)
        action     : "Upgrade" | "At max rarity" | "No DB match" | "Protected"
    """
    items = load_item_db(db_path)
    if not items:
        return []

    by_param, by_base, by_family = build_db_indices(items)
    rows: list[dict] = []

    for inv_item in get_all_items(doc):
        db_item = find_db_item(inv_item, by_param, by_base)

        if db_item is None:
            rows.append({'inv_item': inv_item, 'db_item': None, 'upgrade': None, 'action': 'No DB match'})
            continue

        if not _is_upgrade_safe(db_item):
            rows.append({'inv_item': inv_item, 'db_item': db_item, 'upgrade': None, 'action': 'Protected'})
            continue

        upgrade = find_best_upgrade(db_item, by_family, target_rarity)
        if upgrade is None:
            rows.append({'inv_item': inv_item, 'db_item': db_item, 'upgrade': None, 'action': 'At max rarity'})
        else:
            rows.append({'inv_item': inv_item, 'db_item': db_item, 'upgrade': upgrade, 'action': 'Upgrade'})

    return rows


def apply_upgrades(rows: list[dict]) -> tuple[int, int]:
    """Apply all rows whose action is ``'Upgrade'`` to the live document.

    Returns ``(applied, skipped)``.
    """
    applied = skipped = 0
    for row in rows:
        if row['action'] != 'Upgrade':
            continue
        upgrade = row['upgrade']
        inv_item = row['inv_item']
        new_params = upgrade.get('item_params_path', '')
        old_params = inv_item.get('item_params', '')
        if not new_params or new_params == old_params:
            skipped += 1
            continue
        try:
            item_ref  = inv_item['item_ref']
            stack_ref = inv_item['stack_ref']
            item_ref['ItemParams'] = new_params
            item_ref['ItemId'] = new_item_guid()
            ensure_equipment_integrity(item_ref, stack_ref, old_params, new_params)
            applied += 1
        except Exception:
            skipped += 1
    return applied, skipped
