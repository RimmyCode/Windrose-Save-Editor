from __future__ import annotations

from dataclasses import dataclass

from windrose_save_editor.bson.types import BSONArray, BSONDoc
from windrose_save_editor.game_data import SKILL_CATEGORIES, TALENT_DESCS, TALENT_NAMES
from windrose_save_editor.inventory.reader import get_progression

# All known skill suffixes per category — sourced from DA_HeroTalentTree.json.
# 37 total nodes across 4 categories.
_ALL_TALENTS: dict[str, list[str]] = {
    "Fencer": [
        "ConsecutiveMeleeHitsBonus",
        "CritChanceForPerfectBlock",
        "DamageForSoloEnemy",
        "HealForKill",
        "LessStaminaForDash",
        "OneHandedDamage",
        "OneHandedMeleeCritChance",
        "PassiveReloadBoostForPerfectBlock",
        "PassiveReloadBoostForPerfectDodge",
        "RiposteDamageBonus",
        "SlashDamage",
    ],
    "Crusher": [
        "Berserk",
        "CrudeDamage",
        "DamageForDeathNearby",
        "DamageForMultipleTargets",
        "DamageResistWithTwoHandedWpn",
        "TemporalHPHealBuff",
        "TwoHandedDamage",
        "TwoHandedMeleeCritChance",
        "TwoHandedStaminaReduced",
    ],
    "Marksman": [
        "ActiveReloadSpeedBonus",
        "ConsecutiveRangeHitsBonus",
        "DamageForAimingState",
        "DamageForDistance",
        "DamageForPointBlank",
        "Overpenetration",
        "PassiveReloadBonus",
        "PierceDamage",
        "RangeCritDamageBonus",
        "RangeDamageBonus",
        "ReloadForKill",
    ],
    "Toughguy": [
        "BlockPostureConsumptionBonus",
        "DamageForManyEnemies",
        "DamageResistForHP",
        "ExtraHP",
        "GlobalDamageResist",
        "HealEffectiveness",
        "MeleeDamageResist",
        "ResistForManyEnemies",
        "SaveOnLowHP",
        "StaminaBonus",
        "TempHPForDamageRecivedBonus",
    ],
}

# Complete node metadata sourced from DA_HeroTalentTree.json.
# Keyed by DA asset name; values carry path and UISlotTag.
_TALENT_NODE_DATA: dict[str, dict[str, str]] = {
    "DA_Talent_Crusher_Berserk":                      {"path": "/R5BusinessRules/EntityProgression/Talents/Crusher/DA_Talent_Crusher_Berserk.DA_Talent_Crusher_Berserk",                                         "UISlotTag": "UI.EntityProgression.TalentTree.Slot.2.3.1"},
    "DA_Talent_Crusher_CrudeDamage":                  {"path": "/R5BusinessRules/EntityProgression/Talents/Crusher/DA_Talent_Crusher_CrudeDamage.DA_Talent_Crusher_CrudeDamage",                                 "UISlotTag": "UI.EntityProgression.TalentTree.Slot.2.1.2"},
    "DA_Talent_Crusher_DamageForDeathNearby":         {"path": "/R5BusinessRules/EntityProgression/Talents/Crusher/DA_Talent_Crusher_DamageForDeathNearby.DA_Talent_Crusher_DamageForDeathNearby",               "UISlotTag": "UI.EntityProgression.TalentTree.Slot.2.3.2"},
    "DA_Talent_Crusher_DamageForMultipleTargets":     {"path": "/R5BusinessRules/EntityProgression/Talents/Crusher/DA_Talent_Crusher_DamageForMultipleTargets.DA_Talent_Crusher_DamageForMultipleTargets",       "UISlotTag": "UI.EntityProgression.TalentTree.Slot.2.3.3"},
    "DA_Talent_Crusher_DamageResistWithTwoHandedWpn": {"path": "/R5BusinessRules/EntityProgression/Talents/Crusher/DA_Talent_Crusher_DamageResistWithTwoHandedWpn.DA_Talent_Crusher_DamageResistWithTwoHandedWpn", "UISlotTag": ""},
    "DA_Talent_Crusher_TemporalHPHealBuff":           {"path": "/R5BusinessRules/EntityProgression/Talents/Crusher/DA_Talent_Crusher_TemporalHPHealBuff.DA_Talent_Crusher_TemporalHPHealBuff",                   "UISlotTag": "UI.EntityProgression.TalentTree.Slot.2.1.3"},
    "DA_Talent_Crusher_TwoHandedDamage":              {"path": "/R5BusinessRules/EntityProgression/Talents/Crusher/DA_Talent_Crusher_TwoHandedDamage.DA_Talent_Crusher_TwoHandedDamage",                         "UISlotTag": "UI.EntityProgression.TalentTree.Slot.2.2.1"},
    "DA_Talent_Crusher_TwoHandedMeleeCritChance":     {"path": "/R5BusinessRules/EntityProgression/Talents/Crusher/DA_Talent_Crusher_TwoHandedMeleeCritChance.DA_Talent_Crusher_TwoHandedMeleeCritChance",       "UISlotTag": "UI.EntityProgression.TalentTree.Slot.2.2.3"},
    "DA_Talent_Crusher_TwoHandedStaminaReduced":      {"path": "/R5BusinessRules/EntityProgression/Talents/Crusher/DA_Talent_Crusher_TwoHandedStaminaReduced.DA_Talent_Crusher_TwoHandedStaminaReduced",         "UISlotTag": "UI.EntityProgression.TalentTree.Slot.2.2.2"},
    "DA_Talent_Fencer_ConsecutiveMeleeHitsBonus":     {"path": "/R5BusinessRules/EntityProgression/Talents/Fencer/DA_Talent_Fencer_ConsecutiveMeleeHitsBonus.DA_Talent_Fencer_ConsecutiveMeleeHitsBonus",         "UISlotTag": "UI.EntityProgression.TalentTree.Slot.1.3.4"},
    "DA_Talent_Fencer_CritChanceForPerfectBlock":     {"path": "/R5BusinessRules/EntityProgression/Talents/Fencer/DA_Talent_Fencer_CritChanceForPerfectBlock.DA_Talent_Fencer_CritChanceForPerfectBlock",         "UISlotTag": "UI.EntityProgression.TalentTree.Slot.1.2.2"},
    "DA_Talent_Fencer_DamageForSoloEnemy":            {"path": "/R5BusinessRules/EntityProgression/Talents/Fencer/DA_Talent_Fencer_DamageForSoloEnemy.DA_Talent_Fencer_DamageForSoloEnemy",                       "UISlotTag": "UI.EntityProgression.TalentTree.Slot.1.2.3"},
    "DA_Talent_Fencer_HealForKill":                   {"path": "/R5BusinessRules/EntityProgression/Talents/Fencer/DA_Talent_Fencer_HealForKill.DA_Talent_Fencer_HealForKill",                                     "UISlotTag": "UI.EntityProgression.TalentTree.Slot.1.3.2"},
    "DA_Talent_Fencer_LessStaminaForDash":            {"path": "/R5BusinessRules/EntityProgression/Talents/Fencer/DA_Talent_Fencer_LessStaminaForDash.DA_Talent_Fencer_LessStaminaForDash",                       "UISlotTag": "UI.EntityProgression.TalentTree.Slot.1.1.2"},
    "DA_Talent_Fencer_OneHandedDamage":               {"path": "/R5BusinessRules/EntityProgression/Talents/Fencer/DA_Talent_Fencer_OneHandedDamage.DA_Talent_Fencer_OneHandedDamage",                             "UISlotTag": "UI.EntityProgression.TalentTree.Slot.1.2.1"},
    "DA_Talent_Fencer_OneHandedMeleeCritChance":      {"path": "/R5BusinessRules/EntityProgression/Talents/Fencer/DA_Talent_Fencer_OneHandedMeleeCritChance.DA_Talent_Fencer_OneHandedMeleeCritChance",           "UISlotTag": "UI.EntityProgression.TalentTree.Slot.1.1.3"},
    "DA_Talent_Fencer_PassiveReloadBoostForPerfectBlock": {"path": "/R5BusinessRules/EntityProgression/Talents/Fencer/DA_Talent_Fencer_PassiveReloadBoostForPerfectBlock.DA_Talent_Fencer_PassiveReloadBoostForPerfectBlock", "UISlotTag": "UI.EntityProgression.TalentTree.Slot.1.3.3"},
    "DA_Talent_Fencer_PassiveReloadBoostForPerfectDodge": {"path": "/R5BusinessRules/EntityProgression/Talents/Fencer/DA_Talent_Fencer_PassiveReloadBoostForPerfectDodge.DA_Talent_Fencer_PassiveReloadBoostForPerfectDodge", "UISlotTag": "UI.EntityProgression.TalentTree.Slot.1.3.3"},
    "DA_Talent_Fencer_RiposteDamageBonus":            {"path": "/R5BusinessRules/EntityProgression/Talents/Fencer/DA_Talent_Fencer_RiposteDamageBonus.DA_Talent_Fencer_RiposteDamageBonus",                       "UISlotTag": ""},
    "DA_Talent_Fencer_SlashDamage":                   {"path": "/R5BusinessRules/EntityProgression/Talents/Fencer/DA_Talent_Fencer_SlashDamage.DA_Talent_Fencer_SlashDamage",                                     "UISlotTag": "UI.EntityProgression.TalentTree.Slot.1.1.1"},
    "DA_Talent_Marksman_ActiveReloadSpeedBonus":      {"path": "/R5BusinessRules/EntityProgression/Talents/Marksman/DA_Talent_Marksman_ActiveReloadSpeedBonus.DA_Talent_Marksman_ActiveReloadSpeedBonus",         "UISlotTag": "UI.EntityProgression.TalentTree.Slot.3.2.2"},
    "DA_Talent_Marksman_ConsecutiveRangeHitsBonus":   {"path": "/R5BusinessRules/EntityProgression/Talents/Marksman/DA_Talent_Marksman_ConsecutiveRangeHitsBonus.DA_Talent_Marksman_ConsecutiveRangeHitsBonus",   "UISlotTag": "UI.EntityProgression.TalentTree.Slot.3.3.1"},
    "DA_Talent_Marksman_DamageForAimingState":        {"path": "/R5BusinessRules/EntityProgression/Talents/Marksman/DA_Talent_Marksman_DamageForAimingState.DA_Talent_Marksman_DamageForAimingState",             "UISlotTag": "UI.EntityProgression.TalentTree.Slot.3.3.2"},
    "DA_Talent_Marksman_DamageForDistance":           {"path": "/R5BusinessRules/EntityProgression/Talents/Marksman/DA_Talent_Marksman_DamageForDistance.DA_Talent_Marksman_DamageForDistance",                   "UISlotTag": "UI.EntityProgression.TalentTree.Slot.3.2.3"},
    "DA_Talent_Marksman_DamageForPointBlank":         {"path": "/R5BusinessRules/EntityProgression/Talents/Marksman/DA_Talent_Marksman_DamageForPointBlank.DA_Talent_Marksman_DamageForPointBlank",               "UISlotTag": "UI.EntityProgression.TalentTree.Slot.3.2.3"},
    "DA_Talent_Marksman_Overpenetration":             {"path": "/R5BusinessRules/EntityProgression/Talents/Marksman/DA_Talent_Marksman_Overpenetration.DA_Talent_Marksman_Overpenetration",                       "UISlotTag": "UI.EntityProgression.TalentTree.Slot.3.3.4"},
    "DA_Talent_Marksman_PassiveReloadBonus":          {"path": "/R5BusinessRules/EntityProgression/Talents/Marksman/DA_Talent_Marksman_PassiveReloadBonus.DA_Talent_Marksman_PassiveReloadBonus",                 "UISlotTag": "UI.EntityProgression.TalentTree.Slot.3.1.1"},
    "DA_Talent_Marksman_PierceDamage":                {"path": "/R5BusinessRules/EntityProgression/Talents/Marksman/DA_Talent_Marksman_PierceDamage.DA_Talent_Marksman_PierceDamage",                             "UISlotTag": "UI.EntityProgression.TalentTree.Slot.3.1.2"},
    "DA_Talent_Marksman_RangeCritDamageBonus":        {"path": "/R5BusinessRules/EntityProgression/Talents/Marksman/DA_Talent_Marksman_RangeCritDamageBonus.DA_Talent_Marksman_RangeCritDamageBonus",             "UISlotTag": "UI.EntityProgression.TalentTree.Slot.3.1.3"},
    "DA_Talent_Marksman_RangeDamageBonus":            {"path": "/R5BusinessRules/EntityProgression/Talents/Marksman/DA_Talent_Marksman_RangeDamageBonus.DA_Talent_Marksman_RangeDamageBonus",                     "UISlotTag": "UI.EntityProgression.TalentTree.Slot.3.2.1"},
    "DA_Talent_Marksman_ReloadForKill":               {"path": "/R5BusinessRules/EntityProgression/Talents/Marksman/DA_Talent_Marksman_ReloadForKill.DA_Talent_Marksman_ReloadForKill",                           "UISlotTag": "UI.EntityProgression.TalentTree.Slot.3.3.3"},
    "DA_Talent_Toughguy_BlockPostureConsumptionBonus":{"path": "/R5BusinessRules/EntityProgression/Talents/Toughguy/DA_Talent_Toughguy_BlockPostureConsumptionBonus.DA_Talent_Toughguy_BlockPostureConsumptionBonus", "UISlotTag": "UI.EntityProgression.TalentTree.Slot.4.2.2"},
    "DA_Talent_Toughguy_DamageForManyEnemies":        {"path": "/R5BusinessRules/EntityProgression/Talents/Toughguy/DA_Talent_Toughguy_DamageForManyEnemies.DA_Talent_Toughguy_DamageForManyEnemies",             "UISlotTag": "UI.EntityProgression.TalentTree.Slot.4.2.3"},
    "DA_Talent_Toughguy_DamageResistForHP":           {"path": "/R5BusinessRules/EntityProgression/Talents/Toughguy/DA_Talent_Toughguy_DamageResistForHP.DA_Talent_Toughguy_DamageResistForHP",                   "UISlotTag": ""},
    "DA_Talent_Toughguy_ExtraHP":                     {"path": "/R5BusinessRules/EntityProgression/Talents/Toughguy/DA_Talent_Toughguy_ExtraHP.DA_Talent_Toughguy_ExtraHP",                                       "UISlotTag": "UI.EntityProgression.TalentTree.Slot.4.3.3"},
    "DA_Talent_Toughguy_GlobalDamageResist":          {"path": "/R5BusinessRules/EntityProgression/Talents/Toughguy/DA_Talent_Toughguy_GlobalDamageResist.DA_Talent_Toughguy_GlobalDamageResist",                 "UISlotTag": "UI.EntityProgression.TalentTree.Slot.4.2.1"},
    "DA_Talent_Toughguy_HealEffectiveness":           {"path": "/R5BusinessRules/EntityProgression/Talents/Toughguy/DA_Talent_Toughguy_HealEffectiveness.DA_Talent_Toughguy_HealEffectiveness",                   "UISlotTag": "UI.EntityProgression.TalentTree.Slot.4.1.1"},
    "DA_Talent_Toughguy_MeleeDamageResist":           {"path": "/R5BusinessRules/EntityProgression/Talents/Toughguy/DA_Talent_Toughguy_MeleeDamageResist.DA_Talent_Toughguy_MeleeDamageResist",                   "UISlotTag": ""},
    "DA_Talent_Toughguy_ResistForManyEnemies":        {"path": "/R5BusinessRules/EntityProgression/Talents/Toughguy/DA_Talent_Toughguy_ResistForManyEnemies.DA_Talent_Toughguy_ResistForManyEnemies",             "UISlotTag": ""},
    "DA_Talent_Toughguy_SaveOnLowHP":                 {"path": "/R5BusinessRules/EntityProgression/Talents/Toughguy/DA_Talent_Toughguy_SaveOnLowHP.DA_Talent_Toughguy_SaveOnLowHP",                               "UISlotTag": "UI.EntityProgression.TalentTree.Slot.4.3.2"},
    "DA_Talent_Toughguy_StaminaBonus":                {"path": "/R5BusinessRules/EntityProgression/Talents/Toughguy/DA_Talent_Toughguy_StaminaBonus.DA_Talent_Toughguy_StaminaBonus",                             "UISlotTag": "UI.EntityProgression.TalentTree.Slot.4.1.3"},
    "DA_Talent_Toughguy_TempHPForDamageRecivedBonus": {"path": "/R5BusinessRules/EntityProgression/Talents/Toughguy/DA_Talent_Toughguy_TempHPForDamageRecivedBonus.DA_Talent_Toughguy_TempHPForDamageRecivedBonus", "UISlotTag": "UI.EntityProgression.TalentTree.Slot.4.1.2"},
}


@dataclass
class SkillEntry:
    node_key: str       # dict key in Nodes (or empty string for nodes not yet in the save)
    category: str       # "Fencer" | "Toughguy" | "Marksman" | "Crusher"
    name: str           # human-readable talent name
    description: str    # from TALENT_DESCS, empty string if not found
    level: int
    max_level: int
    # Internal fields used by set_skill_level; not part of the public API surface
    _talent_key: str    # e.g. "Talent_Fencer_SlashDamage"
    _perk_path: str     # full DA asset path


def _da_to_talent_key(da_path: str) -> str:
    """Convert a DA asset path or DA asset name to a TALENT_NAMES lookup key.

    Examples:
        "/R5BusinessRules/.../DA_Talent_Fencer_SlashDamage.DA_Talent_Fencer_SlashDamage"
            -> "Talent_Fencer_SlashDamage"
        "DA_Talent_Fencer_SlashDamage"
            -> "Talent_Fencer_SlashDamage"
    """
    name = da_path.split('/')[-1].split('.')[0]
    if name.startswith('DA_'):
        name = name[3:]   # strip "DA_" prefix -> "Talent_Fencer_SlashDamage"
    return name


def _talent_perk_path(category: str, skill_suffix: str) -> str:
    """Build the full Perks asset path for a talent, falling back to a canonical pattern."""
    da = f"DA_Talent_{category}_{skill_suffix}"
    return _TALENT_NODE_DATA.get(da, {}).get(
        'path',
        f"/R5BusinessRules/EntityProgression/Talents/{category}/{da}.{da}",
    )


def get_skills(doc: BSONDoc) -> dict[str, list[SkillEntry]]:
    """Return skills grouped by category key (same keys as SKILL_CATEGORIES).

    For each category, all known skills are returned — even those not yet present
    in the save (they appear at level 0 with an empty node_key).
    """
    pp = get_progression(doc)
    tt = pp.get('TalentTree', {})
    nodes = tt.get('Nodes', {})

    # Build a reverse map from perk_path -> (node_key, node_dict, node_data_dict)
    # so we can look up existing save nodes by their canonical perk path.
    save_node_by_perk: dict[str, tuple[str, dict, dict]] = {}
    for k, v in nodes.items():
        if not isinstance(v, dict):
            continue
        nd = v.get('NodeData', {})
        perks = nd.get('Perks', {})
        if perks:
            perk_path = list(perks.values())[0]
            save_node_by_perk[perk_path] = (k, v, nd)

    result: dict[str, list[SkillEntry]] = {}

    for cat_key in SKILL_CATEGORIES:
        entries: list[SkillEntry] = []
        for skill_suffix in _ALL_TALENTS.get(cat_key, []):
            perk_path = _talent_perk_path(cat_key, skill_suffix)
            talent_key = f"Talent_{cat_key}_{skill_suffix}"
            name = TALENT_NAMES.get(talent_key, skill_suffix)
            description = TALENT_DESCS.get(talent_key, '')

            if perk_path in save_node_by_perk:
                k, v, nd = save_node_by_perk[perk_path]
                level = int(v.get('NodeLevel', 0))
                max_level = int(nd.get('MaxNodeLevel', 3))
            else:
                k = ''
                level = 0
                max_level = 3

            entries.append(SkillEntry(
                node_key=k,
                category=cat_key,
                name=name,
                description=description,
                level=level,
                max_level=max_level,
                _talent_key=talent_key,
                _perk_path=perk_path,
            ))

        result[cat_key] = entries

    return result


def set_skill_level(doc: BSONDoc, node_key: str, level: int) -> None:
    """Clamp level to [0, max_level] and write it back into doc in-place.

    If node_key is empty the node does not yet exist in the save — callers should
    use the SkillEntry._perk_path / ._talent_key fields to create it first, or
    obtain the entry from get_skills() and call this function after the node has
    been inserted.  For nodes that already exist this is a pure in-place update.

    Also recalculates TalentTree.ProgressionPoints.
    """
    pp = get_progression(doc)
    tt = pp.get('TalentTree', {})
    nodes = tt.get('Nodes', {})

    node = nodes[node_key]
    nd = node.get('NodeData', {})
    max_level = int(nd.get('MaxNodeLevel', 3))
    clamped = max(0, min(level, max_level))

    # Determine the perk_path from the node's own data.
    perks = nd.get('Perks', {})
    perk_path: str = list(perks.values())[0] if perks else node.get('ActivePerk', '')

    node['ActivePerk'] = perk_path if clamped > 0 else ''
    node['NodeLevel'] = clamped

    tt['ProgressionPoints'] = sum(
        int(n.get('NodeLevel', 0))
        for n in nodes.values()
        if isinstance(n, dict)
    )
