from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap

_UI = Path(__file__).parent.parent / "icons" / "R5" / "Content" / "UI"
_TREE = _UI / "META" / "EntityProgression" / "TalentTree" / "Assets"
_STAT = _UI / "META" / "CharacterInfo" / "StatIcons"
_SLOTS = _UI / "Icons" / "Items" / "Slots"

# Talent DA key → icon file stem (for names that don't follow the direct pattern)
_TALENT_OVERRIDES: dict[str, str] = {
    "DA_Talent_Fencer_CritChanceForPerfectBlock":    "T_Talent_Fencer_DamageForBlock",
    "DA_Talent_Toughguy_HealEffectiveness":          "T_Talent_Toughguy_HealEffectivness",
    "DA_Talent_Crusher_DamageResistWithTwoHandedWpn":"T_Talent_Crusher_DamageResistInAttack",
    "DA_Talent_Toughguy_MeleeDamageResist":          "T_Talent_Toughguy_PhysicalRangeDamageResist",
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


def slot_type_icon(slot_type: str, size: int = 40) -> QPixmap:
    """Equipment slot placeholder icon, e.g. 'Head', 'Torso', 'Ring'."""
    return _px_scaled(str(_SLOTS / f"T_SlotTypeIcon_{slot_type}.png"), size)
