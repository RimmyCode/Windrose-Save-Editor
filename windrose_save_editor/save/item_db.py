from __future__ import annotations

"""Item database loader — reads Item ID Database.html and returns a normalised list.

The HTML file contains an embedded JavaScript array:
    const ITEMS = [ {...}, {...}, ... ];

Each item dict has (after normalisation):
    item_params_path  : str   full ItemParams asset path
    display_name      : str   human-readable name
    category          : str
    item_type         : str   e.g. "Inventory.ItemType.Armor.Torso"
    rarity            : str   "Common" | "Uncommon" | "Rare" | "Epic" | "Legendary" | ""
    max_level         : int | None
    icon_ref          : str   game-relative icon path e.g. "/Game/UI/Icons/Items/Armor/T_ItemIcon_…"
"""

import json
import sys
from pathlib import Path

_CACHE: list[dict] | None = None
_NAME_MAP: dict[str, str] | None = None


def _find_db_path() -> Path | None:
    candidates = [
        Path(getattr(sys, '_MEIPASS', '')) / 'Item ID Database.html',
        Path(__file__).resolve().parent.parent.parent / 'Item ID Database.html',
        Path.cwd() / 'Item ID Database.html',
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def _parse_items_html(html: str) -> list[dict]:
    """Extract the ITEMS JS array from the HTML using json.JSONDecoder."""
    marker = 'const ITEMS = ['
    pos = html.find(marker)
    if pos < 0:
        return []
    arr_pos = pos + len(marker) - 1  # points at '['
    try:
        data, _ = json.JSONDecoder().raw_decode(html, arr_pos)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, ValueError):
        return []


def _normalise(raw: dict) -> dict:
    """Accept both v2 GUI schema and older HTML schema field names."""
    def _str(k: str) -> str:
        return str(raw.get(k) or raw.get(k.replace('_', '')) or '')

    params = (
        raw.get('item_params_path')
        or raw.get('itemParamsPath')
        or raw.get('params')
        or ''
    )
    name = (
        raw.get('display_name')
        or raw.get('displayName')
        or raw.get('name')
        or params.split('/')[-1].split('.')[0]
    )
    return {
        'item_params_path': str(params),
        'display_name':     str(name),
        'category':         _str('category'),
        'item_type':        _str('item_type') or _str('itemType'),
        'rarity':           _str('rarity'),
        'max_level':        int(raw['max_level']) if raw.get('max_level') is not None else None,
        'icon_ref':         str(raw.get('icon_ref') or ''),
    }


def load_item_db(path: Path | None = None, force_reload: bool = False) -> list[dict]:
    """Load and return the normalised item list from *Item ID Database.html*.

    Returns an empty list if the file is not found or cannot be parsed.
    Results are cached after the first successful load.
    """
    global _CACHE
    if _CACHE is not None and not force_reload:
        return _CACHE

    db_path = path or _find_db_path()
    if db_path is None or not db_path.exists():
        _CACHE = []
        return _CACHE

    try:
        html = db_path.read_text(encoding='utf-8', errors='replace')
        raw_list = _parse_items_html(html)
        _CACHE = [_normalise(it) for it in raw_list if isinstance(it, dict)]
    except Exception:
        _CACHE = []

    return _CACHE


def build_db_indices(items: list[dict]) -> tuple[dict, dict, dict]:
    """Build three lookup indices from the item list.

    Returns ``(by_param, by_base, by_family)`` where:
    - *by_param*  maps ``item_params_path``     → db_item  (exact match)
    - *by_base*   maps ``basename``             → db_item  (first match, for fallback)
    - *by_family* maps ``family_key``           → list[db_item]  (rarity variants)
    """
    by_param: dict[str, dict] = {}
    by_base:  dict[str, dict] = {}
    by_family: dict[str, list[dict]] = {}

    for it in items:
        params = it['item_params_path']
        base   = params.split('/')[-1].split('.')[0]
        family = _family_key(it)

        by_param[params] = it
        by_base.setdefault(base, it)
        by_family.setdefault(family, []).append(it)

    return by_param, by_base, by_family


def _family_key(db_item: dict) -> str:
    name = db_item.get('display_name', '').strip().lower()
    if name:
        return name
    base = db_item.get('item_params_path', '').split('/')[-1].split('.')[0].lower()
    for kw in ('_legendary', '_epic', '_rare', '_uncommon', '_common', '_base'):
        base = base.replace(kw, '')
    return base


def find_db_item(inv_item: dict, by_param: dict, by_base: dict) -> dict | None:
    """Look up an inventory item in the DB, trying exact path then basename."""
    params = inv_item.get('item_params', '')
    if params in by_param:
        return by_param[params]
    base = params.split('/')[-1].split('.')[0]
    return by_base.get(base)


def get_display_name(item_params: str) -> str:
    """Return the human-readable display name for an item_params path.

    Falls back to the basename (DA key stem) if the DB has no entry.
    """
    global _NAME_MAP
    if _NAME_MAP is None:
        _NAME_MAP = {}
        for it in load_item_db():
            params = it.get('item_params_path', '')
            base   = params.split('/')[-1].split('.')[0] if params else ''
            name   = it.get('display_name', '')
            if name:
                if params:
                    _NAME_MAP.setdefault(params, name)
                if base:
                    _NAME_MAP.setdefault(base, name)

    base = item_params.split('/')[-1].split('.')[0]
    return _NAME_MAP.get(item_params) or _NAME_MAP.get(base) or ''
