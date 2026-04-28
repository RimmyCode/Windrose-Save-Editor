from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap

_UI        = Path(__file__).parent.parent / "icons" / "R5" / "Content" / "UI"
_TREE      = _UI / "META" / "EntityProgression" / "TalentTree" / "Assets"
_STAT      = _UI / "META" / "CharacterInfo" / "StatIcons"
_ITEMS     = _UI / "Icons" / "Items"
_SLOTS     = _ITEMS / "Slots"
_ARMOR_DIR = _ITEMS / "Armor"
_WEAPON_DIR = _ITEMS / "Weapon"

# Talent DA key → icon file stem (for names that don't follow the direct pattern)
_TALENT_OVERRIDES: dict[str, str] = {
    "DA_Talent_Fencer_CritChanceForPerfectBlock":     "T_Talent_Fencer_DamageForBlock",
    "DA_Talent_Toughguy_HealEffectiveness":           "T_Talent_Toughguy_HealEffectivness",
    "DA_Talent_Crusher_DamageResistWithTwoHandedWpn": "T_Talent_Crusher_DamageResistInAttack",
    "DA_Talent_Toughguy_MeleeDamageResist":           "T_Talent_Toughguy_PhysicalRangeDamageResist",
    # Deep Impact — no matching file; use the armour-penetration icon (closest concept)
    "DA_Talent_Marksman_PierceDamage":                "T_Talent_Marksman_RangeArmorPenBonus",
    # Both "Outnumbered" perks share the same display name; reuse the resist icon for the damage variant
    "DA_Talent_Toughguy_DamageForManyEnemies":        "T_Talent_Toughguy_ResistForManyEnemies",
}

_SLOT_STATE_FILES: dict[str, str] = {
    "learn":    "T_Slot_Learn",
    "nonlearn": "T_Slot_NonLearn",
    "default":  "T_Slot_Default",
    "select":   "T_Slot_Select",
    "broken":   "T_Slot_Broken",
}


@lru_cache(maxsize=None)
def _px(path_str: str) -> QPixmap:
    pm = QPixmap(path_str)
    return pm if not pm.isNull() else QPixmap()


@lru_cache(maxsize=None)
def _px_scaled(path_str: str, size: int) -> QPixmap:
    pm = QPixmap(path_str)
    if pm.isNull():
        return QPixmap()
    return pm.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio,
                     Qt.TransformationMode.SmoothTransformation)


def talent_icon(da_key: str) -> QPixmap:
    """White-on-transparent talent art for a DA talent key."""
    stem = _TALENT_OVERRIDES.get(da_key)
    if stem is None:
        stem = "T_" + da_key[3:]              # DA_Talent_X_Y → T_Talent_X_Y
    return _px(str(_TREE / "Talent_Icons" / f"{stem}.png"))


def slot_frame(state: str) -> QPixmap:
    """Circular slot frame: 'learn' | 'nonlearn' | 'default' | 'select'."""
    name = _SLOT_STATE_FILES.get(state, "T_Slot_Default")
    return _px(str(_TREE / f"{name}.png"))


def talent_tree_bg(size: int = 760) -> QPixmap:
    return _px_scaled(str(_TREE / "T_TalentTree_Background.png"), size)


def branch_icon(category: str, size: int = 56) -> QPixmap:
    return _px_scaled(str(_TREE / f"T_TalentBranch_Icon_{category}.png"), size)


def stat_icon(stat_name: str, size: int = 18) -> QPixmap:
    """stat_name: 'Strength', 'Agility', 'Precision', 'Mastery', 'Vitality', 'Endurance'."""
    return _px_scaled(str(_STAT / f"T_StatIcon_{stat_name}.png"), size)


_SLOT_ICON_MAP: dict[str, str] = {
    "Gloves":   "Hands",
    "Feet":     "Boots",
    "Belt":     "Backpack",
}

# DA item path → icon file stem mappings
_ARMOR_SLOT_TO_SUFFIX: dict[str, str] = {
    "Head":   "Hat",
    "Torso":  "Torso",
    "Legs":   "Legs",
    "Hands":  "Hands",
    "Gloves": "Hands",
    "Feet":   "Feets",
    "Boots":  "Feets",
}
_TIER_TOKENS = frozenset({"Base", "T01", "T02", "T03", "T04"})


def item_icon(item_params: str, size: int = 52) -> QPixmap:
    """Resolve a gameplay item icon from its DA asset path. Returns null QPixmap on miss."""
    stem = item_params.split('/')[-1].split('.')[0]
    if 'Armor' in stem:
        parts = stem.replace('DA_EID_', '', 1).split('_')
        if parts and parts[0] == 'Armor' and len(parts) >= 3:
            slot_key = parts[-1]
            suffix   = _ARMOR_SLOT_TO_SUFFIX.get(slot_key)
            if suffix:
                middle = [p for p in parts[1:-1] if p not in _TIER_TOKENS]
                if middle:
                    fname = f"T_ItemIcon_Armor_{'_'.join(middle)}_{suffix}.png"
                    px    = _px_scaled(str(_ARMOR_DIR / fname), size)
                    if not px.isNull():
                        return px
    return QPixmap()


def slot_type_icon(slot_type: str, size: int = 40) -> QPixmap:
    """Equipment slot placeholder icon, e.g. 'Head', 'Torso', 'Ring'."""
    name = _SLOT_ICON_MAP.get(slot_type, slot_type)
    return _px_scaled(str(_SLOTS / f"T_SlotTypeIcon_{name}.png"), size)
