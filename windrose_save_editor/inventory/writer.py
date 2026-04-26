from __future__ import annotations

import uuid

from windrose_save_editor.bson.types import BSONArray
from windrose_save_editor.game_data import MAX_STACK_COUNT, SHIP_TOKENS

# ── Item type detection ──────────────────────────────────────────────────────
_WEAPON_PREFIXES: tuple[str, ...] = (
    'DA_EID_MeleeWeapon_',
    'DA_EID_RangeWeapon_',
    'DA_EID_Weapon_',
)
_ARMOR_PREFIXES: tuple[str, ...] = (
    'DA_EID_Armor_',
    'DA_EID_Helmet_',
    'DA_EID_Gloves_',
    'DA_EID_Boots_',
    'DA_EID_Legs_',
    'DA_EID_Chest_',
)
_EQUIP_PREFIXES: tuple[str, ...] = _WEAPON_PREFIXES + _ARMOR_PREFIXES


def _is_equipment(item_params: str) -> bool:
    """Return True if the ItemParams path is a weapon or armor."""
    name = item_params.split('/')[-1].split('.')[0]
    return any(name.startswith(p) for p in _EQUIP_PREFIXES)


def _infer_slot_params(mod: dict, slot_id: int) -> str:
    """
    Infer the correct SlotParams for a new slot by looking at existing
    slots in the same module. Falls back to DA_BL_Slot_Default.
    """
    slots = mod.get('Slots', {})
    for s in slots.values():
        sp = s.get('SlotParams', '')
        if sp:
            return sp
    return '/R5BusinessRules/Inventory/SlotsParams/DA_BL_Slot_Default.DA_BL_Slot_Default'


# ── Public writer functions ──────────────────────────────────────────────────

def new_item_guid() -> str:
    return uuid.uuid4().hex.upper()


def blank_item(item_params_path: str, level: int = 1, max_level: int = 15) -> dict:
    """Create a new item entry matching the game's save format.
    Equipment gets a level attribute; consumables/stackables get empty Attributes.
    """
    # Attributes and Effects must be BSONArray (0x04) not plain dict (0x03)
    attrs = BSONArray()
    if _is_equipment(item_params_path):
        attrs = BSONArray({
            '0': {
                'MaxValue': max_level,
                'Tag': {'TagName': 'Inventory.Item.Attribute.Level'},
                'Value': max(1, level),
            }
        })
    return {
        'Attributes': attrs,
        'Effects':    BSONArray(),
        'ItemId':     new_item_guid(),
        'ItemParams': item_params_path
    }


def ensure_equipment_integrity(
    item: dict,
    stack: dict,
    old_params: str,
    new_params: str,
) -> None:
    """Enforce count=1 and level≥1 when swapping to equipment; zero level when leaving equipment.

    Call this after writing new_params into item['ItemParams'].
    """
    was_equip = _is_equipment(old_params)
    now_equip = _is_equipment(new_params)

    if now_equip:
        stack['Count'] = 1
        attrs = item.get('Attributes', {})
        level_attr = None
        for a in attrs.values():
            if isinstance(a, dict) and 'Level' in a.get('Tag', {}).get('TagName', ''):
                level_attr = a
                break
        if level_attr is None:
            item.setdefault('Attributes', {})['0'] = {
                'MaxValue': 15,
                'Tag': {'TagName': 'Inventory.Item.Attribute.Level'},
                'Value': 1,
            }
        elif level_attr.get('Value', 0) < 1:
            level_attr['Value'] = 1
    elif was_equip and not now_equip:
        for a in item.get('Attributes', {}).values():
            if isinstance(a, dict) and 'Level' in a.get('Tag', {}).get('TagName', ''):
                a['Value'] = 0
                break


def _item_can_stack(item_params: str) -> bool:
    """Path-based stackability check used when item DB is unavailable."""
    low = item_params.lower()
    if _is_equipment(item_params):
        return False
    if '/jewelry/' in low:
        return False
    if '/ship/' in low:
        return False
    if '/invisible/' in low or '/reputation/' in low:
        return False
    if '/quest/' in low:
        return False
    if '/npc/' in low:
        return False
    if 'lantern' in low:
        return False
    return True


def max_all_levels(doc: dict) -> list[str]:
    """Set every item's Level attribute to its MaxValue. Returns changelog entries."""
    from windrose_save_editor.inventory.reader import get_all_items
    changes: list[str] = []
    for it in get_all_items(doc):
        attrs = it['attrs_ref']
        if not isinstance(attrs, dict):
            continue
        for a in attrs.values():
            if not isinstance(a, dict):
                continue
            if 'Level' not in a.get('Tag', {}).get('TagName', ''):
                continue
            max_val = int(a.get('MaxValue', it['max_level'] or 15))
            old_val = int(a.get('Value', 0))
            if old_val != max_val:
                a['Value'] = max_val
                changes.append(f"Max level: {it['item_name']} {old_val} -> {max_val}")
            break
    return changes


def max_safe_stacks(doc: dict, max_count: int = MAX_STACK_COUNT) -> tuple[int, int, int]:
    """Set count to *max_count* for stackable items; fix non-stackable items to count=1.

    Returns ``(changed, skipped, fixed)`` where:
    - *changed*  = items raised to max_count
    - *skipped*  = non-stackable items whose count was already 1 (untouched)
    - *fixed*    = non-stackable items whose count was >1 and was corrected to 1
    """
    from windrose_save_editor.inventory.reader import get_all_items
    changed = skipped = fixed = 0
    for it in get_all_items(doc):
        stack = it['stack_ref']
        if not isinstance(stack, dict) or 'Count' not in stack:
            continue
        old = stack['Count']
        if _item_can_stack(it['item_params']):
            if old != max_count:
                stack['Count'] = max_count
                changed += 1
        else:
            if old != 1:
                stack['Count'] = 1
                fixed += 1
            else:
                skipped += 1
    return changed, skipped, fixed


def get_ship_items(doc: dict) -> list:
    """Return inventory items whose path contains a ship-related token."""
    from windrose_save_editor.inventory.reader import get_all_items
    return [
        it for it in get_all_items(doc)
        if any(tok in it['item_params'].lower() for tok in SHIP_TOKENS)
    ]


def max_ship_levels(doc: dict) -> list[str]:
    """Set all ship item Level attributes to their MaxValue. Returns changelog entries."""
    changes: list[str] = []
    for it in get_ship_items(doc):
        attrs = it['attrs_ref']
        if not isinstance(attrs, dict):
            continue
        for a in attrs.values():
            if not isinstance(a, dict):
                continue
            if 'Level' not in a.get('Tag', {}).get('TagName', ''):
                continue
            max_val = int(a.get('MaxValue', it['max_level'] or 15))
            old_val = int(a.get('Value', 0))
            if old_val != max_val:
                a['Value'] = max_val
                changes.append(f"Ship max level: {it['item_name']} {old_val} -> {max_val}")
            break
    return changes


def blank_slot_with_item(
    item_params_path: str,
    level: int = 1,
    count: int = 1,
    slot_id: int = 0,
    mod: dict | None = None,
) -> dict:
    slot_params = (
        _infer_slot_params(mod, slot_id)
        if mod is not None
        else '/R5BusinessRules/Inventory/SlotsParams/DA_BL_Slot_Default.DA_BL_Slot_Default'
    )
    return {
        'IsPersonalSlot': False,
        'ItemsStack': {
            'Count': count,
            'Item': blank_item(item_params_path, level)
        },
        'SlotId': slot_id,
        'SlotParams': slot_params
    }
