from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from .location import find_save_root


def list_backups(save_dir: Path) -> list[Path]:
    """Find backups — checks Steam root level (all DBs) and Players level."""
    backups: list[Path] = []
    root = find_save_root(save_dir)

    # Full-root backups (preferred)
    for d in root.parent.iterdir():
        if d.is_dir() and d.name.startswith(root.name + "_backup_"):
            backups.append(d)

    # Old Players-only backups
    for d in save_dir.parent.iterdir():
        if d.is_dir() and d.name.startswith(save_dir.name + "_backup_"):
            backups.append(d)

    return sorted(set(backups), key=lambda d: d.name, reverse=True)


def save_backup(save_dir: Path) -> Path:
    """
    Back up the entire Steam ID folder so Accounts + Players + Worlds
    are all captured together at the same point in time.

    Prints progress to stdout (CLI behaviour preserved).
    Returns the path of the created backup directory.
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    root = find_save_root(save_dir)
    backup = root.parent / f"{root.name}_backup_{ts}"

    print(f"  Backing up full save root: {root.name}  (Accounts + Players + Worlds)...")
    shutil.copytree(root, backup, ignore=shutil.ignore_patterns("LOCK"))
    print(f"✓ Backup saved: {backup}")
    return backup


def restore_backup(save_dir: Path) -> bool:
    """
    Interactively restore a backup chosen by the user.

    Lists available backups, prompts for a selection via input(), then
    renames the current save folder to *_broken and moves the chosen
    backup into its place.

    Prints progress to stdout and calls input() (CLI behaviour preserved).
    Returns True on success, False if cancelled or no backups found.
    """
    backups = list_backups(save_dir)
    if not backups:
        print("  No backups found.")
        return False

    root = find_save_root(save_dir)
    print()
    print("  Available backups (newest first):")
    for i, b in enumerate(backups):
        is_full = b.name.startswith(root.name + "_backup_")
        tag = "[full]" if is_full else "[players only]"
        ts = b.name.split("_backup_")[-1]
        print(f"    {i}) {ts}  {tag}")
    print()

    try:
        idx = int(input("  Which backup to restore? (number): "))
        chosen = backups[idx]
    except (ValueError, IndexError):
        print("  Cancelled.")
        return False

    is_root_backup = chosen.name.startswith(root.name + "_backup_")
    restore_target = root if is_root_backup else save_dir

    broken_path = restore_target.parent / (restore_target.name + "_broken")
    if broken_path.exists():
        shutil.rmtree(broken_path)
    restore_target.rename(broken_path)
    chosen.rename(restore_target)

    scope = (
        "full save (Accounts + Players + Worlds)" if is_root_backup else "Players only"
    )
    print(f"  ✓ Restored {scope}: {chosen.name}")
    print(f"  ✓ Old save kept as: {broken_path.name}")
    print()
    print("  Launch game to verify, then re-run editor to make your edits.")
    return True
