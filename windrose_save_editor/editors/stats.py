from __future__ import annotations

from dataclasses import dataclass

from windrose_save_editor.bson.types import BSONDoc
from windrose_save_editor.game_data import STAT_NAMES
from windrose_save_editor.inventory.reader import get_progression


@dataclass
class StatEntry:
    node_key: str   # dict key in Nodes (e.g. "0", "1")
    name: str       # human-readable (e.g. "Strength")
    level: int
    max_level: int


def get_stats(doc: BSONDoc) -> list[StatEntry]:
    """Return all stat nodes from the StatTree, sorted by numeric node key."""
    pp = get_progression(doc)
    st = pp.get('StatTree', {})
    nodes = st.get('Nodes', {})

    entries: list[StatEntry] = []
    for k, v in sorted(nodes.items(), key=lambda x: int(x[0])):
        if not isinstance(v, dict):
            continue
        nd = v.get('NodeData', {})
        perks = nd.get('Perks', {})
        perk_path = list(perks.values())[0] if perks else ''
        perk_name = perk_path.split('/')[-1].split('.')[0] if perk_path else f'Node{k}'
        name = STAT_NAMES.get(perk_name, perk_name)
        level = int(v.get('NodeLevel', 0))
        max_level = int(nd.get('MaxNodeLevel', 60))
        entries.append(StatEntry(node_key=k, name=name, level=level, max_level=max_level))

    return entries


def set_stat_level(doc: BSONDoc, node_key: str, level: int) -> None:
    """Clamp level to [0, max_level] and write it back into doc in-place.

    Also recalculates StatTree.ProgressionPoints as the sum of all node levels.
    """
    pp = get_progression(doc)
    st = pp.get('StatTree', {})
    nodes = st.get('Nodes', {})

    node = nodes[node_key]
    nd = node.get('NodeData', {})
    max_level = int(nd.get('MaxNodeLevel', 60))
    clamped = max(0, min(level, max_level))
    node['NodeLevel'] = clamped

    st['ProgressionPoints'] = sum(
        int(n.get('NodeLevel', 0))
        for n in nodes.values()
        if isinstance(n, dict)
    )
