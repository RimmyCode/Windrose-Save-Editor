"""
Editor service layer tests — no input(), no print(), pure functions only.
"""
import pytest

from windrose_save_editor.editors.stats import StatEntry, get_stats, set_stat_level
from windrose_save_editor.editors.skills import SkillEntry, get_skills, set_skill_level


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_stat_node(perk_path: str, level: int = 10, max_level: int = 60) -> dict:
    return {
        "NodeLevel": level,
        "NodeData": {
            "Perks": {"0": perk_path},
            "MaxNodeLevel": max_level,
        },
    }


def _make_skill_node(perk_path: str, level: int = 1, max_level: int = 3) -> dict:
    return {
        "NodeLevel": level,
        "NodeData": {
            "Perks": {"0": perk_path},
            "MaxNodeLevel": max_level,
        },
    }


def _stat_doc(nodes: dict) -> dict:
    return {
        "PlayerMetadata": {
            "PlayerProgression": {
                "StatTree": {"Nodes": nodes}
            }
        }
    }


def _skill_doc(nodes: dict) -> dict:
    return {
        "PlayerMetadata": {
            "PlayerProgression": {
                "TalentTree": {"Nodes": nodes}
            }
        }
    }


STRENGTH_PATH  = "/Game/R5/Stats/DA_Strength_Stat.DA_Strength_Stat"
AGILITY_PATH   = "/Game/R5/Stats/DA_Agility_Stat.DA_Agility_Stat"
# Canonical paths from _TALENT_NODE_DATA (EntityProgression, not TalentTrees)
FENCER_DASH    = "/R5BusinessRules/EntityProgression/Talents/Fencer/DA_Talent_Fencer_LessStaminaForDash.DA_Talent_Fencer_LessStaminaForDash"
CRUSHER_DAMAGE = "/R5BusinessRules/EntityProgression/Talents/Crusher/DA_Talent_Crusher_TwoHandedDamage.DA_Talent_Crusher_TwoHandedDamage"


# ── Stats ─────────────────────────────────────────────────────────────────────

def test_get_stats_returns_stat_entries():
    doc = _stat_doc({
        "0": _make_stat_node(STRENGTH_PATH, level=20),
        "1": _make_stat_node(AGILITY_PATH,  level=15),
    })
    stats = get_stats(doc)
    assert len(stats) == 2
    names = {s.name for s in stats}
    assert "Strength" in names
    assert "Agility" in names


def test_get_stats_empty_tree():
    doc = _stat_doc({})
    assert get_stats(doc) == []


def test_set_stat_level_updates_doc():
    doc = _stat_doc({"0": _make_stat_node(STRENGTH_PATH, level=10)})
    set_stat_level(doc, "0", 30)
    assert doc["PlayerMetadata"]["PlayerProgression"]["StatTree"]["Nodes"]["0"]["NodeLevel"] == 30


def test_set_stat_level_clamps_to_max():
    doc = _stat_doc({"0": _make_stat_node(STRENGTH_PATH, level=10, max_level=60)})
    set_stat_level(doc, "0", 999)
    assert doc["PlayerMetadata"]["PlayerProgression"]["StatTree"]["Nodes"]["0"]["NodeLevel"] == 60


def test_set_stat_level_clamps_to_zero():
    doc = _stat_doc({"0": _make_stat_node(STRENGTH_PATH, level=10)})
    set_stat_level(doc, "0", -5)
    assert doc["PlayerMetadata"]["PlayerProgression"]["StatTree"]["Nodes"]["0"]["NodeLevel"] == 0


# ── Skills ────────────────────────────────────────────────────────────────────

def test_get_skills_groups_by_category():
    doc = _skill_doc({
        "0": _make_skill_node(FENCER_DASH,    level=2),
        "1": _make_skill_node(CRUSHER_DAMAGE, level=1),
    })
    skills = get_skills(doc)
    assert "Fencer" in skills
    assert "Crusher" in skills
    # The node with the Fencer perk path at level=2 should appear in Fencer entries
    fencer_levels = {e.level for e in skills["Fencer"] if e.node_key == "0"}
    assert 2 in fencer_levels
    crusher_levels = {e.level for e in skills["Crusher"] if e.node_key == "1"}
    assert 1 in crusher_levels


def test_get_skills_empty_tree():
    """get_skills always returns all 42 talents; unset nodes come back with level=0."""
    doc = _skill_doc({})
    skills = get_skills(doc)
    assert set(skills.keys()) == {"Fencer", "Toughguy", "Marksman", "Crusher"}
    assert all(e.level == 0 for entries in skills.values() for e in entries)


def test_set_skill_level_updates_doc():
    doc = _skill_doc({"0": _make_skill_node(FENCER_DASH, level=1)})
    set_skill_level(doc, "0", 3)
    assert doc["PlayerMetadata"]["PlayerProgression"]["TalentTree"]["Nodes"]["0"]["NodeLevel"] == 3


def test_set_skill_level_clamps_to_max():
    doc = _skill_doc({"0": _make_skill_node(FENCER_DASH, level=1, max_level=3)})
    set_skill_level(doc, "0", 99)
    assert doc["PlayerMetadata"]["PlayerProgression"]["TalentTree"]["Nodes"]["0"]["NodeLevel"] == 3


def test_skill_entry_has_name_and_description():
    doc = _skill_doc({"0": _make_skill_node(FENCER_DASH, level=2)})
    skills = get_skills(doc)
    fencer_skills = skills.get("Fencer", [])
    # The entry matched to node "0" should have level=2
    matched = next((s for s in fencer_skills if s.node_key == "0"), None)
    assert matched is not None
    assert matched.level == 2
    assert matched.name  # non-empty display name
    assert matched.description  # has a description from TALENT_DESCS
