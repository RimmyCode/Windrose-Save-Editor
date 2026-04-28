from __future__ import annotations

from typing import TypedDict

from windrose_save_editor.bson.types import BSONDoc, BSONInt64


class ItemRecord(TypedDict):
    path: str
    module: int
    slot: int
    item_name: str
    item_params: str
    item_id: str
    level: int | None
    max_level: int | None
    count: int
    stack_ref: dict      # mutable ref into doc — used by editors
    mod_ref: dict
    slot_ref: dict
    item_ref: dict
    attrs_ref: dict


def get_all_items(doc: BSONDoc) -> list[ItemRecord]:
    """
    Returns a flat list of item records with context for display and editing.
    Each record: { path, module, slot, item_name, level, max_level, item_id, item_params }
    """
    items: list[ItemRecord] = []
    inventory = doc.get('Inventory', {})
    modules   = inventory.get('Modules', {})

    for mod_idx, mod in sorted(modules.items(), key=lambda x: int(x[0])):
        if not isinstance(mod, dict): continue
        slots = mod.get('Slots', {})
        if not isinstance(slots, dict): continue
        for slot_idx, slot in sorted(slots.items(), key=lambda x: int(x[0])):
            if not isinstance(slot, dict): continue
            stack = slot.get('ItemsStack', {})
            if not isinstance(stack, dict): continue
            item = stack.get('Item', {})
            if not isinstance(item, dict) or not item.get('ItemParams'): continue

            attrs   = item.get('Attributes', {})
            level: int | None   = None
            max_lvl: int | None = None
            if isinstance(attrs, dict):
                for a in attrs.values():
                    if isinstance(a, dict) and 'Level' in a.get('Tag', {}).get('TagName', ''):
                        level   = a.get('Value')
                        max_lvl = a.get('MaxValue')
                        break

            params = item.get('ItemParams', '')
            raw_key = params.split('/')[-1].split('.')[0] if '/' in params else params
            try:
                from windrose_save_editor.save.item_db import get_display_name
                name = get_display_name(params) or raw_key
            except Exception:
                name = raw_key

            items.append(ItemRecord(
                path=f'Inventory.Modules.{mod_idx}.Slots.{slot_idx}',
                module=int(mod_idx),
                slot=int(slot_idx),
                item_name=name,
                item_params=params,
                item_id=item.get('ItemId', ''),
                level=level,
                max_level=max_lvl,
                count=stack.get('Count', 1),
                stack_ref=stack,
                mod_ref=mod,
                slot_ref=slot,
                item_ref=item,
                attrs_ref=attrs,
            ))
    return items


def get_module_capacity(mod: dict) -> int:
    """
    Return the total slot count for a module.
    Priority:
      1. Sum of CountSlots in AdditionalSlotsData (what the game stores)
      2. Highest used slot index + 1 (minimum lower bound)
      3. Default of 8 for completely empty modules
    """
    # AdditionalSlotsData holds the actual capacity grants
    total = 0
    for v in (mod.get('AdditionalSlotsData') or {}).values():
        if isinstance(v, dict):
            cs = v.get('CountSlots', 0)
            total += int(cs) if isinstance(cs, (int, BSONInt64)) else 0

    # ExtendCountSlots from backpack items
    ext = mod.get('ExtendCountSlots', 0)
    total += int(ext) if isinstance(ext, (int, BSONInt64)) else 0

    # Lower bound from highest occupied slot
    slots = mod.get('Slots') or {}
    if slots:
        max_used = max(int(k) for k in slots.keys())
        total = max(total, max_used + 1)

    return total if total > 0 else 8


def slot_has_item(slot: dict) -> bool:
    """Return True if this slot actually contains an item (non-empty ItemParams)."""
    params = slot.get('ItemsStack', {}).get('Item', {}).get('ItemParams', '')
    return bool(params)


def get_empty_slots(doc: BSONDoc, module: int = 0) -> list[int]:
    """
    Return slot indices that have no item, scanning from index 0 upward
    through the full capacity of the module.
    """
    mods     = doc.get('Inventory', {}).get('Modules', {})
    mod      = mods.get(str(module), {})
    slots    = mod.get('Slots', {})
    capacity = get_module_capacity(mod)
    empty: list[int] = []
    for i in range(0, capacity):      # scan all slots from the beginning
        slot = slots.get(str(i))
        if slot is None or not slot_has_item(slot):
            empty.append(i)
    return empty


def get_progression(doc: BSONDoc) -> dict:
    return doc.get('PlayerMetadata', {}).get('PlayerProgression', {})
