from __future__ import annotations

"""Heuristic save-field scanner for map/recipe utilities.

Walks the entire BSON document tree and identifies fields whose key path
matches known map or recipe tokens.  The caller gets a list of candidate
dicts describing what would change; it can then apply all or a subset.
"""

from typing import Any

from windrose_save_editor.bson.types import BSONArray, BSONDoc
from windrose_save_editor.game_data import (
    MAP_PROTECTED_TOKENS,
    MAP_SCAN_TOKENS,
    RECIPE_PROTECTED_TOKENS,
    RECIPE_SCAN_TOKENS,
)


def _path_to_str(path: tuple[str, ...]) -> str:
    return '.'.join(path)


def _path_has_any(path_str: str, tokens: tuple[str, ...]) -> bool:
    low = path_str.lower()
    return any(tok in low for tok in tokens)


def _walk_save_tree(
    obj: Any,
    path: tuple[str, ...] = (),
) -> Any:
    """Yield (path, value) for every node in a nested BSON document."""
    yield path, obj
    if isinstance(obj, (dict, BSONArray)):
        items = obj.items()
    else:
        return
    for k, v in items:
        yield from _walk_save_tree(v, path + (str(k),))


def _candidate_action(path: tuple[str, ...], value: Any, mode: str) -> Any:
    """Return the proposed new value for *value* at *path*, or None if not a candidate."""
    p = _path_to_str(path)
    low = p.lower()

    if mode == 'map':
        if _path_has_any(p, MAP_PROTECTED_TOKENS):
            return None
        if not _path_has_any(p, MAP_SCAN_TOKENS):
            return None
        if 'fog' in low or 'fow' in low:
            if isinstance(value, bool) and value is True:
                return False
            if isinstance(value, int) and value != 0:
                return 0
            if isinstance(value, float) and value != 0.0:
                return 0.0
        elif any(tok in low for tok in (
            'discover', 'visited', 'revealed', 'unlocked', 'known',
            'fasttravel', 'fast_travel', 'marker',
        )):
            if isinstance(value, bool) and value is False:
                return True
            if isinstance(value, int) and value == 0:
                return 1
            if isinstance(value, float) and value == 0.0:
                return 1.0
        return None

    if mode == 'recipe':
        if _path_has_any(p, RECIPE_PROTECTED_TOKENS):
            return None
        if not _path_has_any(p, RECIPE_SCAN_TOKENS):
            return None
        if any(tok in low for tok in (
            'unlocked', 'known', 'learned', 'discovered', 'available', 'enabled',
        )):
            if isinstance(value, bool) and value is False:
                return True
            if isinstance(value, int) and value == 0:
                return 1
        return None

    return None


def scan_candidates(
    doc: BSONDoc,
    mode: str = 'map',
    limit: int = 5_000,
) -> list[dict]:
    """Return candidate fields that the scanner would modify.

    Each entry is a dict with keys:
    - ``path``     : tuple of str keys leading to the field
    - ``path_str`` : dot-separated string version of the path
    - ``old``      : current value
    - ``new``      : proposed value
    """
    rows: list[dict] = []
    for path, value in _walk_save_tree(doc):
        if len(rows) >= limit:
            break
        action = _candidate_action(path, value, mode)
        if action is None:
            continue
        rows.append({
            'path':     path,
            'path_str': _path_to_str(path),
            'old':      value,
            'new':      action,
        })
    return rows


def set_path_value(doc: BSONDoc, path: tuple[str, ...], value: Any) -> None:
    """Write *value* at the nested location described by *path*."""
    cur: Any = doc
    for key in path[:-1]:
        if isinstance(cur, (dict, BSONArray)):
            cur = cur[key]
        else:
            raise KeyError(f"Cannot traverse {key!r} in {type(cur).__name__}")
    cur[path[-1]] = value


def apply_candidates(doc: BSONDoc, candidates: list[dict]) -> tuple[int, int]:
    """Apply a list of scanner candidates to *doc* in-place.

    Returns ``(applied, skipped)`` counts.
    """
    applied = skipped = 0
    for cand in candidates:
        try:
            set_path_value(doc, cand['path'], cand['new'])
            applied += 1
        except Exception:
            skipped += 1
    return applied, skipped


def count_save_nodes(doc: BSONDoc) -> tuple[int, int]:
    """Return ``(total_nodes, primitive_fields)`` by walking the full tree."""
    total = primitives = 0
    for _, value in _walk_save_tree(doc):
        total += 1
        if not isinstance(value, (dict, BSONArray, list)):
            primitives += 1
    return total, primitives
