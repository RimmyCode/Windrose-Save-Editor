from __future__ import annotations

import uuid

from windrose_save_editor.bson.types import BSONArray

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
