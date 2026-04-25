from __future__ import annotations

import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from windrose_save_editor.bson.parser import parse_bson
from windrose_save_editor.bson.serializer import serialize_bson_doc
from windrose_save_editor.bson.types import BSONDoc
from windrose_save_editor.rocksdb.manifest import parse_manifest
from windrose_save_editor.rocksdb.wal import WalEntry, read_wal, write_wal

try:
    import msvcrt as _msvcrt  # type: ignore[import]
except ImportError:
    _msvcrt = None  # type: ignore[assignment]

try:
    import psutil as _psutil  # type: ignore[import]
except ImportError:
    _psutil = None  # type: ignore[assignment]

# Game process names to look for
_GAME_PROCESS_NAMES: list[str] = ["R5.exe", "Windrose.exe", "R5-Win64-Shipping.exe"]


@dataclass
class SaveSession:
    save_dir: Path
    wal_path: Path
    player_key: bytes
    doc: BSONDoc
    original_bson: bytes
    seq: int
    cf_id: int
    batch_count: int
    modified: bool = False
    backed_up: bool = False


def verify_wal(wal_path: Path, expected_key: bytes) -> bool:
    """Read back the WAL we just wrote and confirm it parses correctly."""
    try:
        entry: WalEntry | None = read_wal(wal_path)
        if entry is None:
            print("  [VERIFY] FAIL — WAL reads as empty")
            return False
        if entry.player_key != expected_key:
            print(
                f"  [VERIFY] FAIL — key mismatch: "
                f"{entry.player_key} vs {expected_key}"
            )
            return False
        doc = parse_bson(entry.bson_bytes)
        if not doc.get("_guid"):
            print("  [VERIFY] FAIL — BSON missing _guid")
            return False
        print(
            f"  [VERIFY] OK — seq={entry.sequence} "
            f"key={entry.player_key.decode()} "
            f"bson={len(entry.bson_bytes):,}B"
        )
        return True
    except Exception as e:
        print(f"  [VERIFY] FAIL — {e}")
        return False


def write_via_rocksdb(
    save_dir: Path,
    cf_id: int,
    player_key: bytes,
    bson_bytes: bytes,
) -> bool:
    """
    Write the modified BSON into a new WAL file with the correct sequence
    number from the MANIFEST so RocksDB replays it without complaint.

    Writes to a NEW file number (current + 1) rather than overwriting the
    existing WAL, so other column-family data is not lost.
    """
    log_files = sorted(
        save_dir.glob("*.log"),
        key=lambda f: int(f.stem) if f.stem.isdigit() else 0,
    )
    if not log_files:
        print("  [ERROR] No .log file found in save directory.")
        return False

    manifest = parse_manifest(save_dir)
    last_sequence = manifest.last_sequence
    log_number = manifest.log_number

    if last_sequence == 0:
        print("  [WARN] Could not read last_sequence from MANIFEST")
        last_sequence = 50000

    # Scan every existing WAL and advance past the highest sequence already
    # written.  The MANIFEST is not updated between editor saves, so checking
    # only the manifest would reuse the same sequence on a second save.
    max_wal_sequence = 0
    for existing_log in log_files:
        try:
            entry = read_wal(existing_log)
            if entry is not None:
                max_wal_sequence = max(max_wal_sequence, entry.sequence)
        except Exception:
            # Ignore unrelated / corrupt / non-player WAL fragments
            pass

    write_seq = max(last_sequence, max_wal_sequence) + 1

    current_num = int(log_files[-1].stem)
    new_wal_path = save_dir / f"{current_num + 1:06d}.log"

    print(f"  MANIFEST: last_seq={last_sequence}  log_num={log_number}")
    print(f"  Writing new WAL: {new_wal_path.name}  seq={write_seq}")

    write_wal(new_wal_path, write_seq, cf_id, player_key, bson_bytes)

    print("  Verifying WAL readback…", end=" ")
    if not verify_wal(new_wal_path, player_key):
        print("  WAL write may be corrupted.")
        return False

    print("✓ WAL verified and ready")
    return True


def _wait_for_game_exit() -> None:
    """
    Ask the user to quit the game normally (via in-game menu), then wait
    until all game processes are gone.  A normal quit flushes all databases
    cleanly, preventing partial WAL writes that cause infinite loading.
    """
    if _psutil is None:
        input("  Close the game completely, then press Enter…")
        return

    def game_running() -> bool:
        for p in _psutil.process_iter(["name", "cmdline"]):
            try:
                if p.info["name"] and any(
                    name.lower() == p.info["name"].lower()
                    for name in _GAME_PROCESS_NAMES
                ):
                    return True
                # On Linux / Proton, check the full cmdline (case-insensitive)
                if sys.platform != "win32" and p.info["cmdline"]:
                    cmdline = " ".join(p.info["cmdline"]).lower()
                    if any(name.lower() in cmdline for name in _GAME_PROCESS_NAMES):
                        return True
            except (_psutil.NoSuchProcess, _psutil.AccessDenied):
                pass
        return False

    if not game_running():
        return  # already closed — proceed immediately

    print()
    print("  ┌──────────────────────────────────────────────────────────┐")
    print("  │  QUIT THE GAME NOW via the in-game menu (Esc → Quit).   │")
    print("  │  Do NOT Alt+F4 or use Task Manager.                      │")
    print("  │  The editor will write your changes once it's closed.    │")
    print("  └──────────────────────────────────────────────────────────┘")
    print()
    print("  Waiting for game to close… (press S to skip if already closed)")
    print("  ", end="", flush=True)

    skip = threading.Event()

    def watch_key() -> None:
        if sys.platform == "win32" and _msvcrt is not None:
            while not skip.is_set():
                if _msvcrt.kbhit():
                    if _msvcrt.getch().lower() == b"s":
                        skip.set()
                time.sleep(0.05)
        else:
            import select
            import termios
            import tty

            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setcbreak(fd)
                while not skip.is_set():
                    if select.select([sys.stdin], [], [], 0.05)[0]:
                        if sys.stdin.read(1).lower() == "s":
                            skip.set()
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    watcher = threading.Thread(target=watch_key, daemon=True)
    watcher.start()

    while not skip.is_set() and game_running():
        time.sleep(1)
        print(".", end="", flush=True)

    skip.set()
    if not game_running():
        time.sleep(2)
        print(" closed!")
    else:
        print(" skipped.")
    print()


def commit_changes(session: SaveSession) -> bool:
    """
    Serialize the modified doc from *session* and write it as a NEW WAL file.

    The existing WAL is left untouched so other column-family data
    (ship, buildings, etc.) is not lost.  The new file has a higher log number
    and sequence, so RocksDB replays it last and player changes win.

    Returns True on success, False if the write was aborted or failed.
    """
    print("\nSerializing BSON…", end=" ", flush=True)
    new_bson = serialize_bson_doc(session.doc)
    print(f"{len(new_bson):,} bytes")

    # Byte-level check only applies to unmodified saves (serialiser regression
    # test).  When the user made changes the BSON will intentionally differ.
    if not session.modified:
        if new_bson != session.original_bson:
            diffs = sum(
                1 for a, b in zip(new_bson, session.original_bson) if a != b
            )
            first = next(
                i
                for i, (a, b) in enumerate(zip(new_bson, session.original_bson))
                if a != b
            )
            print(
                "\n[ERROR] BSON is not byte-perfect "
                "(no changes were made but output differs)!"
            )
            print(f"  {diffs} differing bytes, first at offset {first}")
            print(f"  Original byte: 0x{session.original_bson[first]:02x}")
            print(f"  New byte:      0x{new_bson[first]:02x}")
            print(
                "  Context orig:  "
                f"{session.original_bson[max(0, first - 4):first + 8].hex()}"
            )
            print(
                "  Context new:   "
                f"{new_bson[max(0, first - 4):first + 8].hex()}"
            )
            print("\nSave aborted — your backup is safe.")
            return False
        print("✓ BSON byte-perfect round-trip verified")
    else:
        print("✓ BSON serialized with changes")

    _wait_for_game_exit()

    print("Writing to database…", end=" ", flush=True)
    ok = write_via_rocksdb(session.save_dir, session.cf_id, session.player_key, new_bson)
    if ok:
        print("done")
        print("✓ Written via RocksDB API directly into SST/WAL")
        return True

    print()
    print("  [ERROR] RocksDB direct write failed. Your backup is safe.")
    print("  Restore it via option 9 if needed.")
    return False
