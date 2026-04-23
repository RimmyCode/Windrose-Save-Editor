#!/usr/bin/env python3
"""
Community Item ID Visual Guide Generator
=========================================
Recursively scans a directory for .json item definition files,
parses them, and outputs:
  1. item_guide.html   — filterable/sortable visual item database
  2. fmodel_export.txt — asset paths to batch-export icons from FModel
  3. fmodel_script.py  — optional FModel automation script

Localization:
  Place your locres exported as "game.json" anywhere inside the items
  directory (or its root). The script finds it automatically and uses it
  to resolve all display names, descriptions, and vanity text.

Usage:
    python parse_items.py <items_directory> [output_directory]

Example:
    python parse_items.py "C:/Game/Items" "./output"
"""

import json
import re
import sys
from pathlib import Path
from datetime import datetime

# ─────────────────────────────────────────────────────────────────────────────
#  Constants
# ─────────────────────────────────────────────────────────────────────────────

RARITY_ORDER = {
    "Legendary": 0,
    "Epic":      1,
    "Rare":      2,
    "Uncommon":  3,
    "Common":    4,
    "Unknown":   5,
}

RARITY_COLORS = {
    "Legendary": "#f59e0b",
    "Epic":      "#a855f7",
    "Rare":      "#3b82f6",
    "Uncommon":  "#22c55e",
    "Common":    "#9ca3af",
    "Unknown":   "#6b7280",
}

# ─────────────────────────────────────────────────────────────────────────────
#  Localization loader  (game.json = exported locres)
# ─────────────────────────────────────────────────────────────────────────────

def load_locres(root: Path) -> dict:
    """
    Search for game.json anywhere under root and load it as the locres table.
    Returns a nested dict: { namespace: { key: string } }
    Returns an empty dict if not found.
    """
    candidates = list(root.rglob("game.json"))
    if not candidates:
        print("  [INFO] No game.json found — display names will use key fallback.")
        return {}

    path = candidates[0]
    if len(candidates) > 1:
        print(f"  [INFO] Multiple game.json found, using: {path}")
    else:
        print(f"  [INFO] Locres loaded: {path}")

    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        # Validate: should be { namespace(str): { key(str): value(str) } }
        if isinstance(data, dict) and all(isinstance(v, dict) for v in data.values()):
            total = sum(len(v) for v in data.values())
            print(f"         {len(data)} namespaces · {total:,} localization strings")
            return data
        else:
            print("  [WARN] game.json has unexpected structure — ignoring.")
            return {}
    except Exception as e:
        print(f"  [WARN] Could not load game.json: {e}")
        return {}


def resolve_loc(locres: dict, table_id: str, key: str, fallback: str = "") -> str:
    """
    Look up a localized string.
    table_id corresponds to the namespace in the locres (e.g. 'InventoryItems').
    Returns fallback if not found.
    """
    if not locres or not table_id or not key:
        return fallback
    namespace = locres.get(table_id, {})
    return namespace.get(key, fallback)


def key_to_friendly(key: str) -> str:
    """Last-resort name from a raw key when locres has no entry."""
    name = re.sub(r"_ItemName$", "", key)
    name = re.sub(r"^[A-Z]+_", "", name, count=1)   # strip prefix like EID_, DID_
    return name.replace("_", " ").strip()


# ─────────────────────────────────────────────────────────────────────────────
#  Field helpers  (UE JSONs often serialize missing values as the string "None")
# ─────────────────────────────────────────────────────────────────────────────

def sd(val):
    """Safe dict — return val if dict, else {}."""
    return val if isinstance(val, dict) else {}

def sl(val):
    """Safe list — return val if list, else []."""
    return val if isinstance(val, list) else []

def sv(val, fallback=""):
    """Safe string — strip and return val unless empty/'None', else fallback."""
    if isinstance(val, str) and val.strip() not in ("", "None"):
        return val.strip()
    return fallback


# ─────────────────────────────────────────────────────────────────────────────
#  UE path helpers
# ─────────────────────────────────────────────────────────────────────────────

def extract_blueprint_path(item_class_str: str):
    """Pull the /Game/... path out of a BlueprintGeneratedClass string."""
    if not item_class_str:
        return None
    match = re.search(r"'(/Game/[^']+)'", item_class_str)
    if match:
        return match.group(1)
    if item_class_str.startswith("/Game/"):
        return item_class_str
    return None


def icon_asset_path(texture_str: str) -> str:
    """
    Strip the UE object-name suffix so FModel gets just the asset path.
    /Game/UI/.../T_Icon.T_Icon  →  /Game/UI/.../T_Icon
    """
    if not texture_str:
        return ""
    return texture_str.split(".")[0]


# ─────────────────────────────────────────────────────────────────────────────
#  Item parser
# ─────────────────────────────────────────────────────────────────────────────

def parse_item_file(filepath: Path, locres: dict, root: Path, icons_only: bool = False) -> dict | None:
    """
    Parse a single .json item definition.
    Returns None if the file is invalid or (when icons_only=True) has no icon.
    """
    try:
        with open(filepath, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
    except Exception as e:
        print(f"  [WARN] Could not read {filepath.name}: {e}")
        return None

    gpp   = sd(data.get("InventoryItemGppData"))
    ui    = sd(data.get("InventoryItemUIData"))
    equip = sd(gpp.get("InventoryEquipment"))

    # ── Core fields ───────────────────────────────────────────────────────
    item_tag  = sv(sd(gpp.get("ItemTag")).get("TagName"),  "None")
    item_type = sv(sd(gpp.get("ItemType")).get("TagName"), "None")
    rarity    = sv(gpp.get("Rarity"), "Unknown")
    category  = sv(ui.get("Category"), "Unknown")

    # ── Localization keys ─────────────────────────────────────────────────
    name_table = sv(sd(ui.get("ItemName")).get("TableId"))
    name_key   = sv(sd(ui.get("ItemName")).get("Key"), filepath.stem)

    desc_table = sv(sd(ui.get("ItemDescription")).get("TableId"))
    desc_key   = sv(sd(ui.get("ItemDescription")).get("Key"))

    vanity_table = sv(sd(ui.get("VanityText")).get("TableId"))
    vanity_key   = sv(sd(ui.get("VanityText")).get("Key"))

    # ── Resolved strings ──────────────────────────────────────────────────
    resolved_name = resolve_loc(locres, name_table, name_key)
    display_name  = resolved_name if resolved_name else key_to_friendly(name_key)
    name_resolved = bool(resolved_name)  # flag for UI

    description  = resolve_loc(locres, desc_table, desc_key)
    vanity_text  = resolve_loc(locres, vanity_table, vanity_key)

    # ── Icon ──────────────────────────────────────────────────────────────
    raw_texture = sv(ui.get("ItemTexture"))
    if icons_only and not raw_texture:
        return None
    icon_ref = icon_asset_path(raw_texture)

    # ── ItemParams (for save editor) ──────────────────────────────────────
    # Derived from file path relative to the export root.
    # e.g. .../R5BusinessRules/InventoryItems/.../DA_EID_Foo.json
    #   → /R5BusinessRules/InventoryItems/.../DA_EID_Foo.DA_EID_Foo
    try:
        rel = filepath.relative_to(root).with_suffix('')
        rel_str = str(rel).replace('\\', '/').replace('\\', '/')
        # UE plugin paths on disk: Plugins/PluginName/Content/...
        # UE asset paths in-engine: /PluginName/...
        # Strip the Plugins/ prefix and /Content/ segment if present.
        if rel_str.startswith('Plugins/'):
            rel_str = rel_str[len('Plugins/'):]          # drop "Plugins/"
        # Remove /Content/ segment (e.g. R5BusinessRules/Content/Foo → R5BusinessRules/Foo)
        rel_str = rel_str.replace('/Content/', '/')
        stem = filepath.stem
        item_params_path = f'/{rel_str}.{stem}'
    except ValueError:
        item_params_path = ''

    # ── Blueprint / spawn ─────────────────────────────────────────────────
    raw_class      = sv(equip.get("ItemClass"))
    blueprint_path = extract_blueprint_path(raw_class)

    # ── Stats ─────────────────────────────────────────────────────────────
    main_stat_data = sd(ui.get("StatCurveMainStatsData"))
    main_stat      = sv(main_stat_data.get("Stat"))

    secondary_stats = [
        sv(s.get("Stat"))
        for s in sl(ui.get("StatCurveSecondaryStatsData"))
        if isinstance(s, dict) and sv(s.get("Stat"))
    ]

    # ── Attributes ────────────────────────────────────────────────────────
    attributes = sl(gpp.get("Attributes"))
    max_level  = None
    for attr in attributes:
        if isinstance(attr, dict) and "Level" in sv(sd(attr.get("Tag")).get("TagName")):
            max_level = attr.get("MaxValue")
            break

    return {
        "filename":       filepath.stem,
        "display_name":   display_name,
        "name_resolved":  name_resolved,
        "item_name_key":  name_key,
        "description":    description,
        "vanity_text":    vanity_text,
        "item_tag":       item_tag,
        "item_type":      item_type,
        "rarity":         rarity,
        "category":       category,
        "icon_ref":        icon_ref,
        "item_params_path": item_params_path,
        "blueprint_path":  blueprint_path,
        "main_stat":      main_stat,
        "secondary_stats": secondary_stats,
        "max_level":      max_level,
        "weight":         gpp.get("Weight", 0),
        "keep_on_death":  gpp.get("bKeepInInventoryOnDeath", False),
    }


# ─────────────────────────────────────────────────────────────────────────────
#  Directory scanner
# ─────────────────────────────────────────────────────────────────────────────

def scan_directory(root: Path, locres: dict, icons_only: bool = False) -> list[dict]:
    """Walk root recursively, skip game.json itself, parse all other .json files."""
    items   = []
    skipped = 0

    # Collect all JSONs, excluding any game.json
    json_files = sorted(
        fp for fp in root.rglob("*.json")
        if fp.name.lower() != "game.json"
    )
    print(f"Found {len(json_files)} item JSON files (game.json excluded)")

    for fp in json_files:
        item = parse_item_file(fp, locres, root, icons_only=icons_only)
        if item:
            items.append(item)
        else:
            skipped += 1

    label = "inventory items" if icons_only else "items"
    skip_reason = " — no icon" if icons_only else ""
    print(f"Parsed {len(items)} {label}  ({skipped} skipped{skip_reason})")
    return items


def sort_items(items: list[dict]) -> list[dict]:
    return sorted(
        items,
        key=lambda x: (
            RARITY_ORDER.get(x["rarity"], 5),
            x["category"].lower(),
            x["display_name"].lower(),
        ),
    )


# ─────────────────────────────────────────────────────────────────────────────
#  FModel export
# ─────────────────────────────────────────────────────────────────────────────

def write_fmodel_export(items: list[dict], out_dir: Path) -> int:
    icon_paths = sorted(set(i["icon_ref"] for i in items if i["icon_ref"]))

    txt_path = out_dir / "fmodel_export.txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("# FModel Asset Export List\n")
        f.write(f"# Generated: {datetime.now().isoformat()}\n")
        f.write(f"# Total icons: {len(icon_paths)}\n\n")
        for p in icon_paths:
            f.write(p + "\n")
    print(f"  → {txt_path}")

    py_path = out_dir / "fmodel_script.py"
    icon_list_repr = json.dumps(icon_paths, indent=4)
    script = f'''#!/usr/bin/env python3
"""
FModel Batch Icon Exporter
Generated: {datetime.now().isoformat()}
Icons: {len(icon_paths)}
"""
import subprocess
from pathlib import Path

FMODEL_EXE = r"C:\\Tools\\FModel\\FModel.exe"
GAME_DIR   = r"C:\\YourGame\\Content"
OUTPUT_DIR = r".\\icons"
AES_KEY    = ""

ICON_PATHS = {icon_list_repr}

def main():
    out = Path(OUTPUT_DIR)
    out.mkdir(parents=True, exist_ok=True)
    for asset_path in ICON_PATHS:
        args = [FMODEL_EXE, "-g", GAME_DIR, "-o", str(out), "--export", asset_path]
        if AES_KEY:
            args += ["--aes", AES_KEY]
        print(f"Exporting: {{asset_path}}")
        r = subprocess.run(args, capture_output=True, text=True)
        if r.returncode != 0:
            print(f"  [ERROR] {{r.stderr.strip()}}")

if __name__ == "__main__":
    main()
    print("Done.")
'''
    with open(py_path, "w", encoding="utf-8") as f:
        f.write(script)
    print(f"  → {py_path}")
    return len(icon_paths)


# ─────────────────────────────────────────────────────────────────────────────
#  HTML builder
# ─────────────────────────────────────────────────────────────────────────────

def build_html(items: list[dict], icon_count: int, has_locres: bool) -> str:

    rarities   = sorted(set(i["rarity"]   for i in items), key=lambda r: RARITY_ORDER.get(r, 9))
    categories = sorted(set(i["category"] for i in items))
    item_types = sorted(set(i["item_type"] for i in items if i["item_type"] and i["item_type"] != "None"))
    stats_all  = sorted(set(s for i in items for s in i["secondary_stats"]))

    items_json       = json.dumps(items, ensure_ascii=False)
    rarity_colors_json = json.dumps(RARITY_COLORS)

    def opts(values, all_label):
        return "\n".join(
            [f'<option value="">{all_label}</option>'] +
            [f'<option value="{v}">{v}</option>' for v in values]
        )

    locres_badge = (
        '<span style="color:#22c55e;font-family:\'Share Tech Mono\',monospace;font-size:.7rem">● locres loaded</span>'
        if has_locres else
        '<span style="color:#f59e0b;font-family:\'Share Tech Mono\',monospace;font-size:.7rem">○ no game.json — fallback names</span>'
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Item ID Visual Guide</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Rajdhani:wght@400;500;600;700&family=Share+Tech+Mono&family=Exo+2:wght@300;400;600&display=swap" rel="stylesheet">
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{
  --bg:#0a0c10;--bg2:#0f1218;--bg3:#161b24;
  --border:#1e2a3a;--border2:#2a3a50;
  --text:#c8d8e8;--text-dim:#5a7090;--text-bright:#e8f0f8;
  --accent:#00c8ff;--accent2:#0070a0;--glow:rgba(0,200,255,.15);
  --font-head:'Rajdhani',sans-serif;
  --font-mono:'Share Tech Mono',monospace;
  --font-body:'Exo 2',sans-serif;
  --row-hover:rgba(0,200,255,.04);
}}
html,body{{min-height:100vh;background:var(--bg);color:var(--text);font-family:var(--font-body);font-size:14px;line-height:1.5}}
body::before{{content:'';position:fixed;inset:0;z-index:0;
  background-image:linear-gradient(rgba(0,200,255,.03) 1px,transparent 1px),linear-gradient(90deg,rgba(0,200,255,.03) 1px,transparent 1px);
  background-size:40px 40px;pointer-events:none}}
.wrap{{position:relative;z-index:1;max-width:1700px;margin:0 auto;padding:0 24px 60px}}
/* Header */
header{{padding:36px 0 24px;border-bottom:1px solid var(--border);margin-bottom:24px;display:flex;align-items:flex-end;gap:24px;flex-wrap:wrap}}
.title-block{{flex:1;min-width:240px}}
header h1{{font-family:var(--font-head);font-size:2.6rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--text-bright);line-height:1;text-shadow:0 0 40px rgba(0,200,255,.4)}}
header h1 span{{color:var(--accent)}}
.subtitle{{font-family:var(--font-mono);font-size:.72rem;color:var(--text-dim);letter-spacing:.06em;margin-top:6px;display:flex;gap:16px;align-items:center}}
.stats-bar{{display:flex;gap:16px;flex-wrap:wrap}}
.stat-pill{{background:var(--bg3);border:1px solid var(--border2);border-radius:4px;padding:6px 14px;font-family:var(--font-mono);font-size:.7rem;color:var(--text-dim);letter-spacing:.06em}}
.stat-pill strong{{color:var(--accent);font-size:.85rem}}
/* Filters */
.filters{{background:var(--bg2);border:1px solid var(--border);border-radius:8px;padding:16px 18px;margin-bottom:18px;display:flex;gap:12px;flex-wrap:wrap;align-items:flex-end}}
.fg{{display:flex;flex-direction:column;gap:4px;flex:1;min-width:150px}}
.fg label{{font-family:var(--font-mono);font-size:.62rem;color:var(--text-dim);letter-spacing:.1em;text-transform:uppercase}}
input,select{{background:var(--bg3);border:1px solid var(--border2);border-radius:4px;color:var(--text);font-family:var(--font-mono);font-size:.78rem;padding:7px 10px;outline:none;transition:border-color .15s,box-shadow .15s;-webkit-appearance:none;appearance:none}}
input:focus,select:focus{{border-color:var(--accent2);box-shadow:0 0 0 2px var(--glow)}}
select{{background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='8' viewBox='0 0 12 8'%3E%3Cpath d='M1 1l5 5 5-5' stroke='%235a7090' stroke-width='1.5' fill='none'/%3E%3C/svg%3E");background-repeat:no-repeat;background-position:right 10px center;padding-right:28px;cursor:pointer}}
.btn{{padding:7px 16px;border-radius:4px;font-family:var(--font-head);font-weight:600;font-size:.85rem;letter-spacing:.06em;text-transform:uppercase;cursor:pointer;border:1px solid;transition:all .15s}}
.btn-primary{{background:var(--accent2);border-color:var(--accent);color:var(--text-bright)}}
.btn-primary:hover{{background:var(--accent);color:#000}}
.btn-ghost{{background:transparent;border-color:var(--border2);color:var(--text-dim)}}
.btn-ghost:hover{{border-color:var(--text-dim);color:var(--text)}}
.filter-actions{{display:flex;gap:8px}}
/* Result bar */
.result-bar{{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;padding:0 2px}}
.result-count{{font-family:var(--font-mono);font-size:.72rem;color:var(--text-dim)}}
.result-count strong{{color:var(--accent)}}
/* Table */
.table-wrap{{border:1px solid var(--border);border-radius:8px;overflow:hidden}}
table{{width:100%;border-collapse:collapse;table-layout:fixed}}
thead{{background:var(--bg3);position:sticky;top:0;z-index:10}}
thead tr{{border-bottom:2px solid var(--border2)}}
th{{font-family:var(--font-head);font-size:.72rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--text-dim);padding:11px 12px;text-align:left;cursor:pointer;user-select:none;white-space:nowrap;transition:color .15s}}
th:hover{{color:var(--accent)}}
th.sorted{{color:var(--accent)}}
th .si{{opacity:.4;margin-left:3px;font-size:.6rem}}
th.sorted .si{{opacity:1}}
th:nth-child(1){{width:36px}}
th:nth-child(2){{width:210px}}
th:nth-child(3){{width:100px}}
th:nth-child(4){{width:120px}}
th:nth-child(5){{width:190px}}
th:nth-child(6){{width:95px}}
th:nth-child(7){{width:160px}}
th:nth-child(8){{width:65px}}
th:nth-child(9){{width:80px}}
tbody tr{{border-bottom:1px solid var(--border);transition:background .1s}}
tbody tr:last-child{{border-bottom:none}}
tbody tr:hover{{background:var(--row-hover)}}
tbody tr.gh{{background:var(--bg3);border-top:2px solid var(--border2)}}
tbody tr.gh td{{font-family:var(--font-head);font-size:.68rem;letter-spacing:.15em;text-transform:uppercase;color:var(--text-dim);padding:6px 12px;font-weight:700}}
td{{padding:9px 12px;vertical-align:middle}}
.dot{{width:10px;height:10px;border-radius:50%;display:inline-block}}
.item-name{{font-family:var(--font-head);font-size:.92rem;font-weight:600;color:var(--text-bright);cursor:pointer;transition:color .15s;letter-spacing:.02em}}
.item-name:hover{{color:var(--accent);text-decoration:underline;text-decoration-color:rgba(0,200,255,.4)}}
.name-key{{font-family:var(--font-mono);font-size:.58rem;color:var(--text-dim);margin-top:1px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.badge{{display:inline-block;font-family:var(--font-mono);font-size:.62rem;letter-spacing:.06em;padding:2px 7px;border-radius:3px;border:1px solid}}
.mono{{font-family:var(--font-mono);font-size:.7rem;color:var(--text-dim)}}
.stat-tag{{display:inline-block;background:rgba(168,85,247,.08);border:1px solid rgba(168,85,247,.2);border-radius:3px;font-family:var(--font-mono);font-size:.6rem;color:#c084fc;padding:1px 5px;margin:1px 2px 1px 0}}
.btn-spawn{{padding:4px 10px;border-radius:3px;border:1px solid rgba(0,200,255,.3);background:rgba(0,200,255,.06);color:var(--accent);font-family:var(--font-mono);font-size:.63rem;letter-spacing:.04em;cursor:pointer;transition:all .15s;white-space:nowrap}}
.btn-spawn:hover{{background:rgba(0,200,255,.15);border-color:var(--accent);box-shadow:0 0 10px rgba(0,200,255,.2)}}
.btn-spawn.no-bp{{opacity:.3;cursor:not-allowed;pointer-events:none}}
/* Modal */
.modal-overlay{{display:none;position:fixed;inset:0;z-index:100;background:rgba(0,0,0,.78);backdrop-filter:blur(5px);align-items:center;justify-content:center}}
.modal-overlay.open{{display:flex}}
.modal{{background:var(--bg2);border:1px solid var(--border2);border-radius:10px;padding:26px 28px;width:min(640px,96vw);box-shadow:0 0 60px rgba(0,200,255,.1);position:relative;max-height:90vh;overflow-y:auto}}
.modal h2{{font-family:var(--font-head);font-size:1.4rem;font-weight:700;letter-spacing:.06em;color:var(--text-bright);margin-bottom:2px}}
.modal-sub{{font-family:var(--font-mono);font-size:.68rem;color:var(--text-dim);margin-bottom:16px;display:flex;gap:12px;align-items:center;flex-wrap:wrap}}
.modal label{{font-family:var(--font-mono);font-size:.62rem;letter-spacing:.1em;color:var(--text-dim);text-transform:uppercase;display:block;margin-bottom:5px}}
.cmd-block{{display:flex;gap:8px;margin-bottom:16px}}
.cmd-input{{flex:1;background:var(--bg3);border:1px solid var(--border2);border-radius:4px;color:var(--accent);font-family:var(--font-mono);font-size:.75rem;padding:8px 10px;outline:none;overflow-x:auto;white-space:nowrap}}
.btn-copy{{padding:8px 14px;background:var(--accent2);border:1px solid var(--accent);border-radius:4px;color:#fff;font-family:var(--font-head);font-weight:700;font-size:.78rem;letter-spacing:.06em;cursor:pointer;transition:all .15s;white-space:nowrap}}
.btn-copy:hover{{background:var(--accent);color:#000}}
.btn-copy.copied{{background:#22c55e;border-color:#22c55e;color:#000}}
.info-grid{{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:14px}}
.mf{{background:var(--bg3);border:1px solid var(--border);border-radius:4px;padding:9px 11px}}
.mf-label{{font-family:var(--font-mono);font-size:.58rem;color:var(--text-dim);letter-spacing:.1em;text-transform:uppercase;margin-bottom:2px}}
.mf-value{{font-family:var(--font-mono);font-size:.72rem;color:var(--text);word-break:break-all}}
.desc-block{{background:var(--bg3);border:1px solid var(--border);border-radius:4px;padding:10px 12px;margin-bottom:10px;font-size:.8rem;line-height:1.6;color:var(--text);white-space:pre-wrap}}
.vanity-block{{background:rgba(168,85,247,.06);border:1px solid rgba(168,85,247,.2);border-radius:4px;padding:9px 12px;margin-bottom:14px;font-style:italic;font-size:.8rem;color:#c084fc;line-height:1.5}}
.modal-close{{position:absolute;top:12px;right:14px;background:none;border:none;color:var(--text-dim);font-size:1.4rem;cursor:pointer;line-height:1;transition:color .15s}}
.modal-close:hover{{color:var(--text-bright)}}
/* Toast */
.toast{{position:fixed;bottom:26px;right:26px;background:var(--bg3);border:1px solid var(--accent2);border-radius:6px;padding:9px 16px;font-family:var(--font-mono);font-size:.72rem;color:var(--accent);box-shadow:0 4px 20px rgba(0,0,0,.5);z-index:200;transform:translateY(70px);opacity:0;transition:all .25s}}
.toast.show{{transform:translateY(0);opacity:1}}
/* Empty */
.empty-state{{text-align:center;padding:60px 0;font-family:var(--font-mono);color:var(--text-dim);font-size:.85rem}}
.empty-state div{{font-size:2rem;margin-bottom:12px;opacity:.3}}
</style>
</head>
<body>
<div class="wrap">

<header>
  <div class="title-block">
    <h1>ITEM <span>ID</span> DATABASE</h1>
    <div class="subtitle">
      <span>Community Visual Guide · {datetime.now().strftime("%Y-%m-%d %H:%M")}</span>
      {locres_badge}
    </div>
  </div>
  <div class="stats-bar">
    <div class="stat-pill">Items <strong id="totalCount">0</strong></div>
    <div class="stat-pill">Icons <strong>{icon_count}</strong></div>
    <div class="stat-pill">Categories <strong>{len(categories)}</strong></div>
    <div class="stat-pill">Rarities <strong>{len(rarities)}</strong></div>
  </div>
</header>

<div class="filters">
  <div class="fg">
    <label>Search</label>
    <input type="text" id="fSearch" placeholder="Name, tag, key…">
  </div>
  <div class="fg">
    <label>Rarity</label>
    <select id="fRarity">{opts(rarities,"All Rarities")}</select>
  </div>
  <div class="fg">
    <label>Category</label>
    <select id="fCategory">{opts(categories,"All Categories")}</select>
  </div>
  <div class="fg">
    <label>Item Type</label>
    <select id="fType">{opts(item_types,"All Types")}</select>
  </div>
  <div class="fg">
    <label>Stat</label>
    <select id="fStat">{opts(stats_all,"All Stats")}</select>
  </div>
  <div class="filter-actions">
    <button class="btn btn-primary" onclick="applyFilters()">Filter</button>
    <button class="btn btn-ghost" onclick="clearFilters()">Clear</button>
  </div>
</div>

<div class="result-bar">
  <div class="result-count">Showing <strong id="visibleCount">0</strong> items</div>
</div>

<div class="table-wrap">
  <table id="itemTable">
    <thead>
      <tr>
        <th onclick="sortTable(0)"><span class="si">⇅</span></th>
        <th onclick="sortTable(1)">Name <span class="si">⇅</span></th>
        <th onclick="sortTable(2)">Rarity <span class="si">⇅</span></th>
        <th onclick="sortTable(3)">Category <span class="si">⇅</span></th>
        <th onclick="sortTable(4)">Type <span class="si">⇅</span></th>
        <th onclick="sortTable(5)">Main Stat <span class="si">⇅</span></th>
        <th>Secondary Stats</th>
        <th onclick="sortTable(7)">Max Lvl <span class="si">⇅</span></th>
        <th>Spawn</th>
      </tr>
    </thead>
    <tbody id="tableBody"></tbody>
  </table>
</div>

<!-- Modal -->
<div class="modal-overlay" id="spawnModal" onclick="closeModal(event)">
  <div class="modal">
    <button class="modal-close" onclick="closeModalDirect()">×</button>
    <h2 id="modalName"></h2>
    <div class="modal-sub" id="modalSub"></div>

    <label>ItemParams — paste this into the Save Editor (option 4)</label>
    <div class="cmd-block">
      <div class="cmd-input" id="modalItemParams"></div>
      <button class="btn-copy" id="copyParamsBtn" onclick="copyItemParams()">Copy</button>
    </div>

    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:5px;margin-top:4px">
      <label style="margin:0;opacity:.6">Blueprint Path (old Summon / reference)</label>
      <button class="btn-ghost btn" style="font-size:.6rem;padding:3px 10px" onclick="openCmdEditor()">✎ Edit Template</button>
    </div>
    <div class="cmd-block">
      <div class="cmd-input" id="modalCmd" style="opacity:.55;font-size:.68rem"></div>
      <button class="btn-copy" id="copyBtn" onclick="copyCmd()" style="opacity:.7">Copy</button>
    </div>

    <div id="descSection" style="display:none">
      <label>Description</label>
      <div class="desc-block" id="modalDesc"></div>
    </div>

    <div id="vanitySection" style="display:none">
      <label>Flavour Text</label>
      <div class="vanity-block" id="modalVanity"></div>
    </div>

    <div class="info-grid">
      <div class="mf"><div class="mf-label">Item Tag</div><div class="mf-value" id="mfTag">—</div></div>
      <div class="mf"><div class="mf-label">Item Type</div><div class="mf-value" id="mfType">—</div></div>
      <div class="mf"><div class="mf-label">Name Key</div><div class="mf-value" id="mfKey">—</div></div>
      <div class="mf"><div class="mf-label">Filename</div><div class="mf-value" id="mfFile">—</div></div>
      <div class="mf" style="grid-column:1/-1"><div class="mf-label">Blueprint Path</div><div class="mf-value" id="mfBp">—</div></div>
      <div class="mf" style="grid-column:1/-1"><div class="mf-label">Icon Asset (FModel)</div><div class="mf-value" id="mfIcon">—</div></div>
    </div>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
const ITEMS = {items_json};
const RC    = {rarity_colors_json};
const RO    = {{"Legendary":0,"Epic":1,"Rare":2,"Uncommon":3,"Common":4,"Unknown":5}};

let filtered = [...ITEMS];
let sortCol = null, sortAsc = true;

function rc(r){{ return RC[r]||'#9ca3af'; }}

function badge(r){{
  const c=rc(r);
  return `<span class="badge" style="color:${{c}};border-color:${{c}}40;background:${{c}}12">${{r}}</span>`;
}}

function renderTable(items){{
  document.getElementById('visibleCount').textContent = items.length;
  const tbody = document.getElementById('tableBody');
  if(!items.length){{
    tbody.innerHTML='<tr><td colspan="9"><div class="empty-state"><div>⌀</div>No items match.</div></td></tr>';
    return;
  }}

  const groups={{}};
  for(const it of items){{
    const k=`${{it.rarity}}||${{it.category}}`;
    (groups[k]=groups[k]||[]).push(it);
  }}
  const gkeys=Object.keys(groups).sort((a,b)=>{{
    const[ra,ca]=a.split('||');const[rb,cb]=b.split('||');
    const d=(RO[ra]??5)-(RO[rb]??5);
    return d!==0?d:ca.localeCompare(cb);
  }});

  let html='';
  for(const gk of gkeys){{
    const[rar,cat]=gk.split('||');
    const col=rc(rar);
    html+=`<tr class="gh"><td colspan="9" style="color:${{col}};border-left:3px solid ${{col}}">${{rar}} · ${{cat}} <span style="opacity:.45;font-weight:400">(${{groups[gk].length}})</span></td></tr>`;
    for(const it of groups[gk]){{
      const hasBp=!!it.blueprint_path;
      const secs=(it.secondary_stats||[]).map(s=>`<span class="stat-tag">${{s}}</span>`).join('');
      const nameClass = it.name_resolved ? 'item-name' : 'item-name' ;
      const dotStyle=`background:${{col}};box-shadow:0 0 5px ${{col}}80`;
      html+=`<tr>
        <td><span class="dot" style="${{dotStyle}}"></span></td>
        <td>
          <div class="${{nameClass}}" onclick="openModal('${{it.filename}}')">${{it.display_name}}</div>
          <div class="name-key">${{it.item_name_key}}</div>
        </td>
        <td>${{badge(it.rarity)}}</td>
        <td><span class="mono">${{it.category}}</span></td>
        <td><span class="mono" style="font-size:.65rem;color:#4080a0">${{it.item_type||'—'}}</span></td>
        <td><span class="mono" style="color:#c084fc">${{it.main_stat||'—'}}</span></td>
        <td>${{secs||'<span class="mono">—</span>'}}</td>
        <td><span class="mono" style="color:#f59e0b">${{it.max_level??'—'}}</span></td>
        <td><button class="btn-spawn${{it.item_params_path?'':' no-bp'}}" onclick="openModal('${{it.filename}}')">${{it.item_params_path?'📋 Add to Save':'N/A'}}</button></td>
      </tr>`;
    }}
  }}
  tbody.innerHTML=html;
}}

function applyFilters(){{
  const s=document.getElementById('fSearch').value.toLowerCase().trim();
  const r=document.getElementById('fRarity').value;
  const c=document.getElementById('fCategory').value;
  const t=document.getElementById('fType').value;
  const st=document.getElementById('fStat').value;
  filtered=ITEMS.filter(it=>{{
    if(r&&it.rarity!==r)return false;
    if(c&&it.category!==c)return false;
    if(t&&it.item_type!==t)return false;
    if(st&&!([it.main_stat,...(it.secondary_stats||[])].includes(st)))return false;
    if(s){{
      const h=[it.display_name,it.item_name_key,it.item_tag,it.category,it.rarity,it.filename,it.description||'',...(it.secondary_stats||[])].join(' ').toLowerCase();
      if(!h.includes(s))return false;
    }}
    return true;
  }});
  if(sortCol!==null)doSort();
  renderTable(filtered);
}}

function clearFilters(){{
  ['fSearch','fRarity','fCategory','fType','fStat'].forEach(id=>{{
    const el=document.getElementById(id);
    if(el.tagName==='INPUT')el.value=''; else el.value='';
  }});
  applyFilters();
}}

const COL_KEYS=[null,'display_name','rarity','category','item_type','main_stat',null,'max_level'];
function sortTable(col){{
  if(!COL_KEYS[col])return;
  sortCol===col?sortAsc=!sortAsc:(sortCol=col,sortAsc=true);
  document.querySelectorAll('th').forEach((th,i)=>{{
    th.classList.toggle('sorted',i===col);
    const si=th.querySelector('.si');
    if(si)si.textContent=i===col?(sortAsc?'↑':'↓'):'⇅';
  }});
  doSort();renderTable(filtered);
}}
function doSort(){{
  const k=COL_KEYS[sortCol];
  filtered.sort((a,b)=>{{
    let va=a[k],vb=b[k];
    if(k==='rarity'){{va=RO[va]??5;vb=RO[vb]??5;}}
    if(va==null)va='';if(vb==null)vb='';
    if(typeof va==='string')va=va.toLowerCase();
    if(typeof vb==='string')vb=vb.toLowerCase();
    return sortAsc?(va<vb?-1:va>vb?1:0):(va>vb?-1:va<vb?1:0);
  }});
}}

function openModal(fn){{
  const it=ITEMS.find(i=>i.filename===fn);if(!it)return;
  const hasBp=!!it.blueprint_path;
  const hasParams=!!it.item_params_path;
  const cmd=hasBp?`Summon "${{it.blueprint_path}}"` : 'No blueprint path available';
  const modalNameEl=document.getElementById('modalName');modalNameEl.textContent=it.display_name;modalNameEl.dataset.filename=fn;
  const col=rc(it.rarity);
  document.getElementById('modalSub').innerHTML=
    `<span style="color:${{col}}">${{it.rarity}}</span> · ${{it.category}} · ${{it.item_type||'—'}}` +
    (it.name_resolved?'':' <span style="color:#f59e0b;font-size:.62rem">(fallback name)</span>');
  document.getElementById('modalItemParams').textContent = it.item_params_path || '(not available — regenerate HTML from updated parse_items.py)';
  document.getElementById('copyParamsBtn').disabled = !hasParams;
  document.getElementById('modalCmd').textContent=cmd;

  const descEl=document.getElementById('descSection');
  const descText=document.getElementById('modalDesc');
  if(it.description){{descEl.style.display='';descText.textContent=it.description;}}
  else descEl.style.display='none';

  const vanEl=document.getElementById('vanitySection');
  const vanText=document.getElementById('modalVanity');
  if(it.vanity_text){{vanEl.style.display='';vanText.textContent=it.vanity_text;}}
  else vanEl.style.display='none';

  document.getElementById('mfTag').textContent=it.item_tag||'—';
  document.getElementById('mfType').textContent=it.item_type||'—';
  document.getElementById('mfKey').textContent=it.item_name_key||'—';
  document.getElementById('mfFile').textContent=it.filename||'—';
  document.getElementById('mfBp').textContent=it.blueprint_path||'(none)';
  document.getElementById('mfIcon').textContent=it.icon_ref||'(none)';

  const cb=document.getElementById('copyBtn');
  cb.disabled=!hasBp;cb.classList.remove('copied');cb.textContent='Copy';
  const cpb=document.getElementById('copyParamsBtn');
  cpb.disabled=!hasParams;cpb.classList.remove('copied');cpb.textContent='Copy';
  document.getElementById('spawnModal').classList.add('open');
}}

function closeModal(e){{if(e.target===document.getElementById('spawnModal'))closeModalDirect();}}
function closeModalDirect(){{document.getElementById('spawnModal').classList.remove('open');}}

function copyItemParams(){{
  const p=document.getElementById('modalItemParams').textContent;
  if(!p||p.startsWith('(')) return;
  navigator.clipboard.writeText(p).then(()=>{{
    const b=document.getElementById('copyParamsBtn');
    b.textContent='Copied!'; b.classList.add('copied');
    showToast('ItemParams copied — paste into Save Editor option 4');
    setTimeout(()=>{{b.textContent='Copy';b.classList.remove('copied');}},2000);
  }});
}}

function copyCmd(){{
  const cmd=document.getElementById('modalCmd').textContent;
  navigator.clipboard.writeText(cmd).then(()=>{{
    const b=document.getElementById('copyBtn');
    b.textContent='Copied!';b.classList.add('copied');
    showToast('Spawn command copied');
    setTimeout(()=>{{b.textContent='Copy';b.classList.remove('copied');}},2000);
  }});
}}

function showToast(msg){{
  const t=document.getElementById('toast');
  t.textContent=msg;t.classList.add('show');
  setTimeout(()=>t.classList.remove('show'),2400);
}}

document.addEventListener('keydown',e=>{{if(e.key==='Escape')closeModalDirect();}});
document.getElementById('fSearch').addEventListener('input',applyFilters);
['fRarity','fCategory','fType','fStat'].forEach(id=>
  document.getElementById(id).addEventListener('change',applyFilters));

document.getElementById('totalCount').textContent=ITEMS.length;
renderTable(filtered);
</script>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main(icons_only: bool = True):
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    items_dir  = Path(sys.argv[1]).resolve()
    output_dir = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else Path("./item_guide_output")

    if not items_dir.exists():
        print(f"[ERROR] Directory not found: {items_dir}")
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"\nScanning: {items_dir}")
    print(f"Output:   {output_dir}\n")

    # 1. Load locres
    print("Loading localization (game.json)…")
    locres = load_locres(items_dir)
    has_locres = bool(locres)

    # 2. Parse items
    print("\nParsing item definitions…")
    items = scan_directory(items_dir, locres, icons_only=icons_only)
    if not items:
        print("[ERROR] No valid items found.")
        sys.exit(1)

    items = sort_items(items)

    # 3. FModel
    print("\nGenerating FModel export…")
    icon_count = write_fmodel_export(items, output_dir)

    # 4. HTML
    print("\nGenerating HTML guide…")
    html_path = output_dir / "item_guide.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(build_html(items, icon_count, has_locres))
    print(f"  → {html_path}")

    resolved = sum(1 for i in items if i["name_resolved"])
    print(f"\n✓ Done!  {len(items)} items · {icon_count} icons · {resolved} names resolved from locres")
    print(f"  Open: {html_path}")


if __name__ == "__main__":
    main()
