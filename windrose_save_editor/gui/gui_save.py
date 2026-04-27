from __future__ import annotations

import shutil
from pathlib import Path

from windrose_save_editor.save.commit import SaveSession, write_via_rocksdb
from windrose_save_editor.save.backup import list_backups, save_backup
from windrose_save_editor.save.location import find_save_root
from windrose_save_editor.bson.serializer import serialize_bson_doc

_GAME_NAMES = {"r5.exe", "windrose.exe", "r5-win64-shipping.exe"}


def is_game_running() -> bool:
    """Return True if a Windrose game process is currently running."""
    try:
        import psutil
        for p in psutil.process_iter(["name"]):
            try:
                name = (p.info.get("name") or "").lower()
                if name in _GAME_NAMES:
                    return True
            except Exception:
                pass
    except ImportError:
        pass
    return False


def gui_commit_changes(session: SaveSession) -> tuple[bool, str]:
    """
    GUI-safe commit: serialise the doc and write a new WAL without ever
    calling input() or blocking on game-exit detection.

    Returns (success, human-readable message).
    """
    new_bson = serialize_bson_doc(session.doc)

    # Regression guard: unmodified saves must round-trip byte-perfect.
    if not session.modified:
        if new_bson != session.original_bson:
            diff = sum(1 for a, b in zip(new_bson, session.original_bson) if a != b)
            return False, (
                f"BSON round-trip check failed ({diff} differing byte(s)). "
                "No changes written — your backup is safe."
            )

    try:
        ok = write_via_rocksdb(
            session.save_dir, session.cf_id, session.player_key, new_bson
        )
    except Exception as exc:
        return False, f"Write error: {exc}"

    if ok:
        session.modified = False
        return True, "Changes written successfully."
    return False, "Write failed — your backup is safe."


def gui_create_backup(save_dir: Path) -> tuple[bool, str]:
    """Create a timestamped backup. Returns (success, message)."""
    try:
        dest = save_backup(save_dir)
        return True, f"Backup saved: {dest.name}"
    except Exception as exc:
        return False, f"Backup failed: {exc}"


def gui_restore_backup(save_dir: Path, chosen: Path) -> tuple[bool, str]:
    """
    Restore *chosen* backup without calling input().
    Renames the current save to *_broken first as a safety net.
    Returns (success, message).
    """
    try:
        root = find_save_root(save_dir)
        is_root = chosen.name.startswith(root.name + "_backup_")
        target = root if is_root else save_dir

        broken = target.parent / (target.name + "_broken")
        if broken.exists():
            shutil.rmtree(broken)
        target.rename(broken)
        chosen.rename(target)

        scope = "full save (Accounts + Players + Worlds)" if is_root else "Players only"
        return True, (
            f"Restored {scope}: {chosen.name}\n"
            f"Old save kept as: {broken.name}\n\n"
            "Launch the game to verify, then re-open the editor."
        )
    except Exception as exc:
        return False, f"Restore failed: {exc}"
