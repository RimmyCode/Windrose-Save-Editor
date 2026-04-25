from __future__ import annotations

"""
SST file reader for Windrose save data.

Reads player data directly from RocksDB SST files via the rocksdb C API
(loaded at runtime through ctypes). Requires a compatible rocksdb.dll
(Windows) or librocksdb.so (Linux) to be discoverable at runtime — either
next to the script, in the game's Steam installation, or on the system
library path.
"""

import ctypes
import ctypes.util
import os
import struct
import sys
from pathlib import Path


def scan_sst_for_player(save_dir: Path) -> tuple[bytes, bytes] | None:
    """
    Read player data from SST files using librocksdb.

    Searches for a compatible rocksdb shared library, opens the database
    read-only with all column families, then fetches the player BSON document
    using the save folder name as the key (which is the player GUID).

    Returns (player_key_bytes, bson_bytes) or None if the library is not
    found, the key is missing, or any RocksDB call fails.
    """
    script_dir = Path(__file__).resolve().parent
    lib_path: Path | None = None
    lib: ctypes.CDLL | None = None

    game_lib_locations: list[Path] = []
    steam_bases: list[Path] = []

    if sys.platform == "win32":
        available_drives: list[str] = []
        if hasattr(os, "listdrives"):
            # Python 3.12+: returns root paths like ['C:\\', 'D:\\']
            available_drives = [d.rstrip(":\\") for d in os.listdrives()]
        else:
            bitmask = ctypes.windll.kernel32.GetLogicalDrives()
            available_drives = [
                chr(ord("A") + i) for i in range(26) if bitmask & (1 << i)
            ]

        for drive in available_drives:
            for p in [
                r"Program Files (x86)/Steam",
                r"Program Files/Steam",
                r"Steam",
                r"SteamLibrary",
            ]:
                base = Path(f"{drive}:/") / p / "steamapps/common"
                if base.exists():
                    steam_bases.append(base)

    elif sys.platform.startswith("linux"):
        steam_bases = [
            Path.home() / ".local/share/Steam/steamapps/common",
            Path.home() / ".steam/steam/steamapps/common",
            Path.home() / ".var/app/com.valvesoftware.Steam/data/Steam/steamapps/common",
        ]

    for steam_base in steam_bases:
        for game_folder in ["Windrose", "R5"]:
            if not (steam_base / game_folder).exists():
                continue
            for found in (steam_base / game_folder).rglob("rocksdb.dll"):
                game_lib_locations.append(found)
            for found in (steam_base / game_folder).rglob("librocksdb.so*"):
                game_lib_locations.append(found)

    _bundle_dir: Path | None = Path(sys._MEIPASS) if hasattr(sys, '_MEIPASS') else None
    _exe_dir = Path(sys.executable).parent
    _bundle_candidates: list[Path] = []
    for _d in filter(None, [_bundle_dir, _exe_dir]):
        _bundle_candidates += [_d / "rocksdb.dll", _d / "librocksdb.so"]

    candidates: list[Path] = game_lib_locations + _bundle_candidates + [
        script_dir / "rocksdb.dll",
        script_dir / "librocksdb.dll",
        script_dir / "librocksdb.so",
        script_dir / "librocksdb.so.8",
        Path("rocksdb.dll"),
        Path("librocksdb.dll"),
        Path("librocksdb.so"),
    ]

    for sys_name in ["rocksdb", "librocksdb", "rocksdb-jemalloc"]:
        found = ctypes.util.find_library(sys_name)
        if found:
            candidates.append(Path(found))

    for candidate in candidates:
        try:
            lib = ctypes.CDLL(str(candidate))
            _ = lib.rocksdb_options_create  # verify C API is present
            lib_path = candidate
            print(f"  Using: {candidate.name}")
            break
        except (OSError, AttributeError):
            continue

    if lib is None:
        lib_name = "librocksdb.so" if sys.platform.startswith("linux") else "rocksdb.dll"
        print(f"  [WARN] {lib_name} not found. Make sure it is in the")
        print(f"         same folder as this script: {script_dir}")
        if sys.platform.startswith("linux"):
            print("  Try: sudo apt install librocksdb-dev  (or your distro's equivalent)")
            print("  Or extract librocksdb.so from the NuGet package (runtimes/linux-x64/native/)")
        else:
            print("  Download from: https://www.nuget.org/packages/RocksDB")
            print("  (open .nupkg with 7-zip, grab rocksdb.dll from runtimes/win-x64/native/)")
        return None

    CF_NAMES = [
        b"default",
        b"R5LargeObjects",
        b"R5BLPlayer",
        b"R5BLShip",
        b"R5BLBuilding",
        b"R5BLActor_BuildingBlock",
    ]
    n = len(CF_NAMES)

    try:
        lib.rocksdb_options_create.restype = ctypes.c_void_p
        lib.rocksdb_readoptions_create.restype = ctypes.c_void_p
        lib.rocksdb_open_for_read_only_column_families.restype = ctypes.c_void_p
        lib.rocksdb_open_for_read_only_column_families.argtypes = [
            ctypes.c_void_p,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_char_p),
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.c_uint8,
            ctypes.POINTER(ctypes.c_char_p),
        ]
        lib.rocksdb_get_cf.restype = ctypes.c_void_p
        lib.rocksdb_get_cf.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_char_p,
            ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_size_t),
            ctypes.POINTER(ctypes.c_char_p),
        ]
        lib.rocksdb_free.argtypes = [ctypes.c_void_p]

        lib.rocksdb_create_iterator_cf.restype = ctypes.c_void_p
        lib.rocksdb_create_iterator_cf.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        lib.rocksdb_iter_seek_to_first.argtypes = [ctypes.c_void_p]
        lib.rocksdb_iter_valid.restype = ctypes.c_uint8
        lib.rocksdb_iter_valid.argtypes = [ctypes.c_void_p]
        lib.rocksdb_iter_key.restype = ctypes.c_char_p
        lib.rocksdb_iter_key.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t)]
        lib.rocksdb_iter_value.restype = ctypes.c_char_p
        lib.rocksdb_iter_value.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t)]
        lib.rocksdb_iter_next.argtypes = [ctypes.c_void_p]

        db_opts = lib.rocksdb_options_create()
        ropts = lib.rocksdb_readoptions_create()
        err = ctypes.c_char_p()
        cf_names_arr = (ctypes.c_char_p * n)(*CF_NAMES)
        cf_opts_arr = (ctypes.c_void_p * n)(
            *[lib.rocksdb_options_create() for _ in range(n)]
        )
        cf_handles = (ctypes.c_void_p * n)()

        db = lib.rocksdb_open_for_read_only_column_families(
            db_opts,
            str(save_dir).encode(),
            n,
            cf_names_arr,
            cf_opts_arr,
            cf_handles,
            ctypes.c_uint8(0),
            ctypes.byref(err),
        )

        if err.value:
            print(f"  [WARN] RocksDB open error: {err.value.decode()}")
            return None

        # Read from R5BLPlayer column family (index 2).
        # The player GUID is the save folder name — use it as the key directly
        # instead of iterating, which is more robust across DLL versions.
        cf_player = cf_handles[2]
        guid = save_dir.name.encode("ascii")
        val_len = ctypes.c_size_t()
        get_err = ctypes.c_char_p()

        val_ptr = lib.rocksdb_get_cf(
            db,
            ropts,
            cf_player,
            guid,
            len(guid),
            ctypes.byref(val_len),
            ctypes.byref(get_err),
        )

        if get_err.value:
            print(f"  [WARN] RocksDB get error: {get_err.value.decode()}")
            return None

        if not val_ptr or val_len.value == 0:
            print(f"  [WARN] Key not found: {guid.decode()}")
            print("  Ensure the game is fully closed and try again.")
            return None

        raw = (ctypes.c_char * val_len.value).from_address(val_ptr)
        val_bytes = bytes(raw)
        lib.rocksdb_free(val_ptr)

        if len(val_bytes) < 4 or struct.unpack_from("<I", val_bytes, 0)[0] != val_len.value:
            print(f"  [WARN] Data at key does not look like BSON ({val_len.value} bytes)")
            return None

        print(f"  Found player: {guid.decode()} ({val_len.value:,} bytes)")
        return guid, val_bytes

    except Exception as e:
        print(f"  [WARN] librocksdb read failed: {e}")
        return None
