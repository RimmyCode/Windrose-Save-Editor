"""
Inventory tests — focused on what matters:
  - get_all_items correctly extracts typed ItemRecords from a synthetic doc
  - slot/capacity logic (drives add-item feature)
  - writer produces valid BSON-compatible dicts
"""
import pytest

from windrose_save_editor.inventory.reader import (
    ItemRecord, get_all_items, get_module_capacity,
    get_empty_slots, slot_has_item,
)
from windrose_save_editor.inventory.writer import (
    blank_item, blank_slot_with_item, new_item_guid,
)
from windrose_save_editor.bson.types import BSONInt64


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_item(params: str, level: int = 5, max_level: int = 15, count: int = 1) -> dict:
    return {
        "ItemsStack": {
            "Count": count,
            "Item": {
                "ItemId": "AABBCCDD" * 4,
                "ItemParams": params,
                "Attributes": {
                    "0": {
                        "Tag": {"TagName": "Inventory.Item.Attribute.Level"},
                        "Value": level,
                        "MaxValue": max_level,
                    }
                },
                "Effects": {},
            },
        },
        "SlotId": 0,
        "IsPersonalSlot": False,
        "SlotParams": "/R5BusinessRules/Inventory/SlotsParams/DA_BL_Slot_Default.DA_BL_Slot_Default",
    }


def _make_doc(slots: dict[str, dict]) -> dict:
    """Build a minimal save doc with one module (index 0) and given slots."""
    return {
        "Inventory": {
            "Modules": {
                "0": {
                    "Slots": slots,
                    "AdditionalSlotsData": {
                        "0": {"CountSlots": 8}
                    },
                }
            }
        }
    }


SWORD_PARAMS = "/R5BusinessRules/InventoryItems/Equipments/Weapons/DA_EID_Sword.DA_EID_Sword"
BOW_PARAMS   = "/R5BusinessRules/InventoryItems/Equipments/Weapons/DA_EID_Bow.DA_EID_Bow"


# ── get_all_items ─────────────────────────────────────────────────────────────

def test_get_all_items_returns_item_records():
    doc = _make_doc({"0": _make_item(SWORD_PARAMS, level=7)})
    items = get_all_items(doc)
    assert len(items) == 1
    item = items[0]
    assert item["module"] == 0
    assert item["slot"] == 0
    assert item["level"] == 7
    assert item["max_level"] == 15
    assert item["count"] == 1
    assert "DA_EID_Sword" in item["item_name"]


def test_get_all_items_empty_doc():
    assert get_all_items({}) == []


def test_get_all_items_skips_empty_slots():
    empty_slot = {"ItemsStack": {"Item": {"ItemParams": ""}}, "SlotId": 1}
    doc = _make_doc({"0": _make_item(SWORD_PARAMS), "1": empty_slot})
    items = get_all_items(doc)
    assert len(items) == 1  # empty slot not included


def test_get_all_items_multiple_items_sorted():
    doc = _make_doc({
        "0": _make_item(SWORD_PARAMS, level=3),
        "3": _make_item(BOW_PARAMS, level=9),
    })
    items = get_all_items(doc)
    assert len(items) == 2
    assert items[0]["slot"] == 0
    assert items[1]["slot"] == 3


def test_item_record_mutation_writes_back_to_doc():
    """Mutating attrs_ref must be reflected in the source doc (the ref contract)."""
    doc = _make_doc({"0": _make_item(SWORD_PARAMS, level=5)})
    items = get_all_items(doc)
    for a in items[0]["attrs_ref"].values():
        if "Level" in a.get("Tag", {}).get("TagName", ""):
            a["Value"] = 99
    # Read back from doc directly
    node = doc["Inventory"]["Modules"]["0"]["Slots"]["0"]["ItemsStack"]["Item"]["Attributes"]["0"]
    assert node["Value"] == 99


# ── Capacity and empty-slot logic ─────────────────────────────────────────────

def test_get_module_capacity_from_additional_slots_data():
    mod = {"AdditionalSlotsData": {"0": {"CountSlots": 12}}}
    assert get_module_capacity(mod) == 12


def test_get_module_capacity_uses_bsonint64():
    mod = {"AdditionalSlotsData": {"0": {"CountSlots": BSONInt64(10)}}}
    assert get_module_capacity(mod) == 10


def test_get_module_capacity_lower_bound_from_occupied_slots():
    mod = {"Slots": {"0": {}, "5": {}}}
    # No AdditionalSlotsData → lower bound = max(5) + 1 = 6
    assert get_module_capacity(mod) == 6


def test_get_module_capacity_default():
    assert get_module_capacity({}) == 8


def test_get_empty_slots_finds_free_slots():
    doc = _make_doc({"0": _make_item(SWORD_PARAMS)})  # slot 0 occupied, 1-7 free
    empty = get_empty_slots(doc, module=0)
    assert 0 not in empty
    assert 1 in empty
    assert len(empty) == 7


def test_get_empty_slots_full_module():
    slots = {str(i): _make_item(SWORD_PARAMS) for i in range(8)}
    doc = _make_doc(slots)
    assert get_empty_slots(doc, module=0) == []


def test_slot_has_item_true_when_params_present():
    slot = _make_item(SWORD_PARAMS)
    assert slot_has_item(slot) is True


def test_slot_has_item_false_when_params_empty():
    slot = {"ItemsStack": {"Item": {"ItemParams": ""}}}
    assert slot_has_item(slot) is False


# ── Writer ────────────────────────────────────────────────────────────────────

def test_new_item_guid_is_32_char_hex():
    guid = new_item_guid()
    assert len(guid) == 32
    assert guid.isupper()
    int(guid, 16)  # raises ValueError if not valid hex


def test_new_item_guid_is_unique():
    assert new_item_guid() != new_item_guid()


def test_blank_item_structure_equipment():
    """Equipment paths get a populated Level attribute."""
    item = blank_item(SWORD_PARAMS, level=3, max_level=15)
    assert item["ItemParams"] == SWORD_PARAMS
    assert len(item["ItemId"]) == 32
    # SWORD_PARAMS is not prefixed DA_EID_MeleeWeapon_ etc, so Attributes is empty
    # Use an actual equipment-style path to test attribute population
    equip_params = "/R5BusinessRules/InventoryItems/DA_EID_Armor_Test.DA_EID_Armor_Test"
    item2 = blank_item(equip_params, level=3, max_level=15)
    attrs = item2["Attributes"]["0"]
    assert attrs["Value"] == 3
    assert attrs["MaxValue"] == 15
    assert "Level" in attrs["Tag"]["TagName"]


def test_blank_item_non_equipment_has_empty_attributes():
    item = blank_item("/some/non/equip/path.path", level=5)
    assert item["Attributes"] == {}


def test_blank_slot_with_item_structure():
    slot = blank_slot_with_item(SWORD_PARAMS, level=2, count=5, slot_id=3)
    assert slot["SlotId"] == 3
    assert slot["ItemsStack"]["Count"] == 5
    assert slot["ItemsStack"]["Item"]["ItemParams"] == SWORD_PARAMS
