from __future__ import annotations

from .skills import SkillEntry, get_skills, max_all_skills, set_skill_level
from .stats import StatEntry, get_stats, max_all_stats, set_stat_level

__all__ = [
    "StatEntry",
    "get_stats",
    "max_all_stats",
    "set_stat_level",
    "SkillEntry",
    "get_skills",
    "max_all_skills",
    "set_skill_level",
]
