from __future__ import annotations

from pathlib import Path


def resolve_save_dir(save_dir: Path) -> Path:
    """
    Recursively search for the Players/<GUID> RocksDB folder.

    The actual save structure is:
      <SteamID>/RocksDB/<version>/Players/<PlayerGUID>/  <- we want this
    Falls back to any directory containing a CURRENT file.
    """
    # Already pointing at the right place
    if (save_dir / "CURRENT").exists():
        return save_dir

    # Prefer a Players/<GUID> subdirectory anywhere in the tree
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

    # Fallback: any subdirectory containing CURRENT (up to 8 levels deep)
    for current_file in save_dir.rglob("CURRENT"):
        folder = current_file.parent
        if list(folder.glob("*.log")):  # must also have a WAL
            rel = folder.relative_to(save_dir)
            print(f"  [INFO] Found save at: {rel}")
            return folder

    return save_dir  # give up, let find_wal produce the real error


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

    save_dir is .../76561197960287777/RocksDB/0.10.0/Players/<GUID>.
    Walk up until a folder that looks like a Steam ID (numeric name, >= 10 chars)
    is found. Falls back to save_dir itself.
    """
    path = save_dir
    for _ in range(8):
        path = path.parent
        if path.name.isdigit() and len(path.name) >= 10:
            return path
    # Fallback: return the Players GUID folder (old behaviour)
    return save_dir
