from __future__ import annotations

import os
import re
import sys
from pathlib import Path

_APP_ID = '3041230'
_PROTON_SAVE_SUFFIX = Path(
    'pfx/drive_c/users/steamuser/AppData/Local/R5/Saved/SaveProfiles'
)


def resolve_save_dir(save_dir: Path) -> Path:
    """
    Recursively search for the Players/<GUID> RocksDB folder.

    The actual save structure is:
      <SteamID>/RocksDB/<version>/Players/<PlayerGUID>/  <- we want this
    Falls back to any directory containing a CURRENT file.
    """
    if (save_dir / "CURRENT").exists():
        return save_dir

    for players_dir in save_dir.rglob("Players"):
        if players_dir.is_dir():
            candidates = [
                d
                for d in players_dir.iterdir()
                if d.is_dir() and (d / "CURRENT").exists()
            ]
            if candidates:
                chosen = candidates[0]
                print(f"  [INFO] Auto-detected player save: ...\\Players\\{chosen.name}")
                return chosen

    for current_file in save_dir.rglob("CURRENT"):
        folder = current_file.parent
        if list(folder.glob("*.log")):
            rel = folder.relative_to(save_dir)
            print(f"  [INFO] Found save at: {rel}")
            return folder

    return save_dir


def find_wal(save_dir: Path) -> Path:
    """Return the most recent WAL (.log) file in save_dir."""
    logs = sorted(save_dir.glob("*.log"))
    if not logs:
        raise FileNotFoundError(
            f"No .log file found in: {save_dir}\n\n"
            f"  Point at the folder that contains CURRENT + *.sst + *.log,\n"
            f'  not a parent folder. Run:  dir "{save_dir}"  to see contents.'
        )
    return logs[-1]


def find_save_root(save_dir: Path) -> Path:
    """
    Find the Steam ID root folder that contains ALL databases
    (Players, Worlds, Accounts).
    """
    path = save_dir
    for _ in range(8):
        path = path.parent
        if path.name.isdigit() and len(path.name) >= 10:
            return path
    return save_dir


# ── Auto-detect helpers ───────────────────────────────────────────────────────

def find_profiles_root() -> Path | None:
    """Return the SaveProfiles folder for the current platform, or None."""
    if sys.platform == 'win32':
        local_app = Path(os.environ.get('LOCALAPPDATA', ''))
        candidate = local_app / 'R5' / 'Saved' / 'SaveProfiles'
        return candidate if candidate.exists() else None

    home = Path.home()
    steam_bases = [
        home / '.local/share/Steam/steamapps/compatdata',
        home / '.steam/steam/steamapps/compatdata',
        home / '.var/app/com.valvesoftware.Steam/data/Steam/steamapps/compatdata',
    ]
    for base in steam_bases:
        candidate = base / _APP_ID / _PROTON_SAVE_SUFFIX
        if candidate.exists():
            return candidate

    result = _find_save_via_vdf(_APP_ID, _PROTON_SAVE_SUFFIX)
    if result:
        print(f"  [INFO] Found save via libraryfolders.vdf: {result}")
    return result


def _find_save_via_vdf(app_id: str, save_suffix: Path) -> Path | None:
    home = Path.home()
    vdf_candidates = [
        home / '.local/share/Steam/steamapps/libraryfolders.vdf',
        home / '.steam/steam/steamapps/libraryfolders.vdf',
        home / '.var/app/com.valvesoftware.Steam/data/Steam/steamapps/libraryfolders.vdf',
    ]
    for vdf_path in vdf_candidates:
        if not vdf_path.exists():
            continue
        try:
            text = vdf_path.read_text(encoding='utf-8', errors='replace')
            for match in re.finditer(r'"path"\s+"([^"]+)"', text):
                lib_root = Path(match.group(1))
                candidate = lib_root / 'steamapps' / 'compatdata' / app_id / save_suffix
                if candidate.exists():
                    return candidate
        except Exception:
            pass
    return None


def account_type(name: str) -> str | None:
    """Return 'Steam', 'Epic', or None."""
    if name.isdigit():
        return 'Steam'
    if re.fullmatch(r'[0-9a-f]{32}', name.lower()):
        return 'Epic'
    return None


def find_accounts(profiles_root: Path) -> list[tuple[Path, str]]:
    """Return sorted (account_dir, type) pairs found under profiles_root."""
    return sorted(
        [(d, account_type(d.name)) for d in profiles_root.iterdir()
         if d.is_dir() and account_type(d.name) is not None],
        key=lambda x: x[0].name,
    )


def find_player_dirs(account_dir: Path) -> list[Path]:
    """Return sorted player save directories under account_dir."""
    players_root = account_dir / 'RocksDB' / '0.10.0' / 'Players'
    if not players_root.exists():
        return []
    return sorted(
        d for d in players_root.iterdir()
        if d.is_dir() and (d / 'CURRENT').exists()
    )


def peek_player_name(player_dir: Path) -> str:
    """Read the PlayerName field from the save without a full parse."""
    from windrose_save_editor.rocksdb.wal import read_wal as _read_wal
    from windrose_save_editor.bson.parser import parse_bson
    try:
        entry = _read_wal(find_wal(player_dir))
        if entry:
            return parse_bson(entry.bson_bytes).get('PlayerName', '')
    except Exception:
        pass
    try:
        from windrose_save_editor.rocksdb.sst import scan_sst_for_player
        result = scan_sst_for_player(player_dir)
        if result:
            return parse_bson(result[1]).get('PlayerName', '')
    except Exception:
        pass
    return ''
