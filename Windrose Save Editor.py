#!/usr/bin/env python3
"""
Windrose Save Editor
=====================
Reads, edits, and writes back Windrose character save files.

The save is a RocksDB database whose WAL stores one giant BSON document:
  key  = player GUID (32-char hex)
  value = BSON document with the entire character state

Usage:
    python windrose_save_editor.py <save_directory>

The save_directory should contain: CURRENT, MANIFEST-*, *.sst, *.log
Typically: %LOCALAPPDATA%\\R5\\Saved\\SaveProfiles\\<character_folder>

ALWAYS back up your save folder before editing!
"""

import struct, sys, os, shutil, uuid, json, copy
from pathlib import Path
from datetime import datetime

# Game process names to look for (add more if needed)
GAME_PROCESS_NAMES = ['R5.exe', 'Windrose.exe', 'R5-Win64-Shipping.exe', 'Windrose-Win64-Shipping.exe']

# CRC32C (Castagnoli) — pure Python, no external dependency.
# crcmod/binascii use CRC32-IEEE which produces wrong checksums for RocksDB.
def _make_crc32c_table():
    POLY = 0x82F63B78  # Castagnoli polynomial (reflected)
    table = []
    for i in range(256):
        crc = i
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ POLY
            else:
                crc >>= 1
        table.append(crc)
    return table

_CRC32C_TABLE = _make_crc32c_table()

def crc32c(data: bytes) -> int:
    crc = 0xFFFFFFFF
    for byte in data:
        crc = (crc >> 8) ^ _CRC32C_TABLE[(crc ^ byte) & 0xFF]
    return crc ^ 0xFFFFFFFF

# ─────────────────────────────────────────────────────────────────────────────
#  BSON helpers
# ─────────────────────────────────────────────────────────────────────────────

class BSONArray(dict):
    """A dict subclass that serializes back as BSON type 0x04 (Array)."""
    pass

class BSONDatetime(int):
    """An int subclass that serializes back as BSON type 0x09 (UTC datetime)."""
    pass

class BSONInt64(int):
    """An int subclass that serializes back as BSON int64 (type 0x12)."""
    pass

# ─────────────────────────────────────────────────────────────────────────────
#  BSON Parser
# ─────────────────────────────────────────────────────────────────────────────

def bson_read_cstring(data: bytes, pos: int) -> tuple[str, int]:
    end = data.index(0, pos)
    return data[pos:end].decode('utf-8', errors='replace'), end + 1

def parse_bson(data: bytes, pos: int = 0) -> dict:
    doc_size = struct.unpack_from('<I', data, pos)[0]
    end = pos + doc_size
    pos += 4
    doc = {}
    while pos < end - 1:
        btype = data[pos]; pos += 1
        if btype == 0:
            break
        name, pos = bson_read_cstring(data, pos)
        if btype == 0x01:   # double
            doc[name] = struct.unpack_from('<d', data, pos)[0]; pos += 8
        elif btype == 0x02: # string
            slen = struct.unpack_from('<I', data, pos)[0]; pos += 4
            doc[name] = data[pos:pos+slen-1].decode('utf-8', errors='replace'); pos += slen
        elif btype == 0x03:  # embedded document
            subdoc_size = struct.unpack_from('<I', data, pos)[0]
            doc[name] = parse_bson(data, pos)
            pos += subdoc_size
        elif btype == 0x04:  # array — preserve type for round-trip
            subdoc_size = struct.unpack_from('<I', data, pos)[0]
            doc[name] = BSONArray(parse_bson(data, pos))
            pos += subdoc_size
        elif btype == 0x05: # binary
            blen = struct.unpack_from('<I', data, pos)[0]; pos += 4
            subtype = data[pos]; pos += 1
            doc[name] = {'$binary': data[pos:pos+blen].hex(), '$subtype': subtype}; pos += blen
        elif btype == 0x08: # bool
            doc[name] = bool(data[pos]); pos += 1
        elif btype == 0x09: # datetime — preserve type
            doc[name] = BSONDatetime(struct.unpack_from('<q', data, pos)[0]); pos += 8
        elif btype == 0x0A: # null
            doc[name] = None
        elif btype == 0x10: # int32
            doc[name] = struct.unpack_from('<i', data, pos)[0]; pos += 4
        elif btype == 0x12: # int64 — preserve type
            doc[name] = BSONInt64(struct.unpack_from('<q', data, pos)[0]); pos += 8
        else:
            raise ValueError(f"Unknown BSON type 0x{btype:02x} at pos {pos-1} field '{name}'")
    return doc

# ─────────────────────────────────────────────────────────────────────────────
#  BSON Serializer
# ─────────────────────────────────────────────────────────────────────────────

def bson_cstring(s: str) -> bytes:
    return s.encode('utf-8') + b'\x00'

def serialize_bson_value(val) -> bytes:
    """Return (type_byte, payload_bytes) for a Python value."""
    if isinstance(val, bool):
        return 0x08, bytes([1 if val else 0])
    elif isinstance(val, int):
        if -2**31 <= val <= 2**31-1:
            return 0x10, struct.pack('<i', val)
        else:
            return 0x12, struct.pack('<q', val)
    elif isinstance(val, float):
        return 0x01, struct.pack('<d', val)
    elif isinstance(val, str):
        encoded = val.encode('utf-8') + b'\x00'
        return 0x02, struct.pack('<I', len(encoded)) + encoded
    elif val is None:
        return 0x0A, b''
    elif isinstance(val, BSONDatetime):
        return 0x09, struct.pack('<q', int(val))
    elif isinstance(val, BSONInt64):
        return 0x12, struct.pack('<q', int(val))
    elif isinstance(val, dict):
        if '$binary' in val:
            raw = bytes.fromhex(val['$binary'])
            return 0x05, struct.pack('<I', len(raw)) + bytes([val.get('$subtype', 0)]) + raw
        elif isinstance(val, BSONArray):
            return 0x04, serialize_bson_doc(val)
        else:
            return 0x03, serialize_bson_doc(val)
    else:
        raise TypeError(f"Cannot serialize type {type(val)}: {val!r}")

def serialize_bson_doc(doc: dict) -> bytes:
    body = b''
    for key, val in doc.items():
        vtype, payload = serialize_bson_value(val)
        body += bytes([vtype]) + bson_cstring(key) + payload
    body += b'\x00'  # terminator
    size = 4 + len(body)
    return struct.pack('<I', size) + body

# ─────────────────────────────────────────────────────────────────────────────
#  RocksDB WAL reader/writer
# ─────────────────────────────────────────────────────────────────────────────

BLOCK_SIZE = 32768

def read_varint(data: bytes, pos: int) -> tuple[int, int]:
    result, shift = 0, 0
    while True:
        b = data[pos]; pos += 1
        result |= (b & 0x7f) << shift
        if not (b & 0x80): break
        shift += 7
    return result, pos

def write_varint(n: int) -> bytes:
    out = []
    while True:
        b = n & 0x7f; n >>= 7
        if n: b |= 0x80
        out.append(b)
        if not n: break
    return bytes(out)

def wal_masked_crc(data: bytes) -> int:
    raw = crc32c(data)
    return (((raw >> 15) | (raw << 17)) + 0xa282ead8) & 0xFFFFFFFF

def read_wal(log_path: Path) -> tuple[int, int, bytes, bytes]:
    """
    Returns (sequence, cf_id, player_key, bson_bytes).
    Reassembles fragmented WAL blocks.
    """
    with open(log_path, 'rb') as f:
        raw = f.read()

    # Reassemble payload from block fragments
    payload = b''
    pos = 0
    while pos < len(raw):
        if pos + 7 > len(raw): break
        # crc(4) + length(2) + type(1)
        length = struct.unpack_from('<H', raw, pos+4)[0]
        rtype  = raw[pos+6]
        chunk  = raw[pos+7:pos+7+length]
        if rtype in (1, 4):   # FULL or LAST
            payload += chunk
        elif rtype in (2, 3): # FIRST or MIDDLE
            payload += chunk
        pos += BLOCK_SIZE

    # WriteBatch header
    if len(payload) < 12:
        return None   # empty WAL — data is in SST files

    # Scan ALL write batches to find the LAST player entry (CF 2, 32-byte key)
    # The game appends multiple batches per session; we want the most recent.
    last_seq         = None
    last_cf_id       = 2
    last_player_key  = None
    last_bson        = None
    last_batch_count = 1

    pos = 0
    while pos + 12 <= len(payload):
        try:
            batch_seq   = struct.unpack_from('<Q', payload, pos)[0]
            batch_count = struct.unpack_from('<I', payload, pos + 8)[0]
            p = pos + 12
            for _ in range(batch_count):
                if p >= len(payload): break
                etype = payload[p]; p += 1
                if etype in (0x01, 0x05):          # default-CF or named-CF value
                    cf_id_entry = 0
                    if etype == 0x05:
                        cf_id_entry, p = read_varint(payload, p)
                    key_len, p = read_varint(payload, p)
                    key        = payload[p:p+key_len];  p += key_len
                    val_len, p = read_varint(payload, p)
                    val        = payload[p:p+val_len];  p += val_len
                    # Player key = CF 2, 32 bytes, large BSON value
                    if (cf_id_entry == 2 and key_len == 32 and val_len > 1000
                            and len(val) >= 4
                            and struct.unpack_from('<I', val, 0)[0] == val_len):
                        last_player_key = key
                        last_bson       = val
                        last_seq        = batch_seq
                elif etype in (0x00, 0x04):         # deletion — skip key only
                    cf_id_entry = 0
                    if etype == 0x04:
                        _, p = read_varint(payload, p)
                    key_len, p = read_varint(payload, p)
                    p += key_len
                else:
                    break   # unknown entry type — stop scanning this batch
            pos = p
        except Exception:
            break  # corrupt / end of WAL

    if last_bson is None or last_seq is None:
        return None

    return last_seq, last_cf_id, last_player_key, last_bson, last_batch_count



def scan_sst_for_player(save_dir: Path) -> tuple[bytes, bytes] | None:
    """
    Read player data from SST files using librocksdb (the same library the
    game uses). Falls back to None if librocksdb is not available.
    Returns (player_key_bytes, bson_bytes) or None.
    """
    import ctypes, ctypes.util

    # Find librocksdb — check next to this script first, then common system names
    script_dir = Path(__file__).resolve().parent
    lib_path = None
    lib = None

    # Search for the game's own rocksdb.dll first — it's guaranteed compatible
    # with the save files since the game wrote them with it.
    game_dll_locations = []
    for steam_base in [
        Path(r'C:/Program Files (x86)/Steam/steamapps/common'),
        Path(r'C:/Program Files/Steam/steamapps/common'),
        Path(r'D:/Steam/steamapps/common'),
        Path(r'D:/SteamLibrary/steamapps/common'),
        Path(r'E:/Steam/steamapps/common'),
        Path(r'E:/SteamLibrary/steamapps/common'),
        Path(r'G:/Steam/steamapps/common'),
        Path(r'G:/SteamLibrary/steamapps/common'),
    ]:
        for game_folder in ['Windrose', 'R5']:
            for dll_path in (steam_base / game_folder).rglob('rocksdb.dll'):
                game_dll_locations.append(dll_path)

    candidates = (
        game_dll_locations +          # game's own DLL (best)
        [
            script_dir / 'rocksdb.dll',
            script_dir / 'librocksdb.dll',
            script_dir / 'librocksdb.so',
            Path('rocksdb.dll'),
            Path('librocksdb.dll'),
        ]
    )
    # Also try system library names via find_library
    for sys_name in ['rocksdb', 'librocksdb.so.8.9', 'librocksdb.so.8']:
        found = ctypes.util.find_library(sys_name)
        if found:
            candidates.append(Path(found))

    for candidate in candidates:
        try:
            lib = ctypes.CDLL(str(candidate))
            # Verify it has the C API we need
            _ = lib.rocksdb_options_create
            lib_path = candidate
            print(f"  Using: {candidate.name}")
            break
        except (OSError, AttributeError):
            continue

    if lib is None:
        print("  [WARN] rocksdb.dll not found. Make sure rocksdb.dll is in the")
        print(f"         same folder as this script: {script_dir}")
        print("  Download from: https://www.nuget.org/packages/RocksDB")
        print("  (open .nupkg with 7-zip, grab rocksdb.dll from runtimes/win-x64/native/)")
        return None

    CF_NAMES = [b'default', b'R5LargeObjects', b'R5BLPlayer',
                b'R5BLShip', b'R5BLBuilding', b'R5BLActor_BuildingBlock']
    n = len(CF_NAMES)

    try:
        lib.rocksdb_options_create.restype     = ctypes.c_void_p
        lib.rocksdb_readoptions_create.restype = ctypes.c_void_p
        lib.rocksdb_open_for_read_only_column_families.restype  = ctypes.c_void_p
        lib.rocksdb_open_for_read_only_column_families.argtypes = [
            ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int,
            ctypes.POINTER(ctypes.c_char_p), ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(ctypes.c_void_p), ctypes.c_uint8,
            ctypes.POINTER(ctypes.c_char_p),
        ]
        lib.rocksdb_get_cf.restype  = ctypes.c_void_p
        lib.rocksdb_get_cf.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
            ctypes.c_char_p, ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(ctypes.c_char_p),
        ]
        lib.rocksdb_free.argtypes = [ctypes.c_void_p]

        db_opts      = lib.rocksdb_options_create()
        ropts        = lib.rocksdb_readoptions_create()
        err          = ctypes.c_char_p()
        cf_names_arr = (ctypes.c_char_p * n)(*CF_NAMES)
        cf_opts_arr  = (ctypes.c_void_p * n)(
            *[lib.rocksdb_options_create() for _ in range(n)])
        cf_handles   = (ctypes.c_void_p * n)()

        db = lib.rocksdb_open_for_read_only_column_families(
            db_opts, str(save_dir).encode(), n,
            cf_names_arr, cf_opts_arr, cf_handles,
            ctypes.c_uint8(0), ctypes.byref(err))

        if err.value:
            print(f"  [WARN] RocksDB open error: {err.value.decode()}")
            return None

        # Read from R5BLPlayer column family (index 2)
        cf_player = cf_handles[2]
        val_len   = ctypes.c_size_t()
        err2      = ctypes.c_char_p()

        # Iterate to find the player key (GUID we may not know ahead of time)
        lib.rocksdb_create_iterator_cf.restype  = ctypes.c_void_p
        lib.rocksdb_create_iterator_cf.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
        lib.rocksdb_iter_seek_to_first.argtypes = [ctypes.c_void_p]
        lib.rocksdb_iter_valid.restype  = ctypes.c_uint8
        lib.rocksdb_iter_valid.argtypes = [ctypes.c_void_p]
        lib.rocksdb_iter_key.restype    = ctypes.c_char_p
        lib.rocksdb_iter_key.argtypes   = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t)]
        lib.rocksdb_iter_value.restype  = ctypes.c_char_p
        lib.rocksdb_iter_value.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t)]
        lib.rocksdb_iter_next.argtypes  = [ctypes.c_void_p]

        lib.rocksdb_get_cf.restype  = ctypes.c_void_p
        lib.rocksdb_get_cf.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
            ctypes.c_char_p, ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(ctypes.c_char_p)
        ]
        lib.rocksdb_free.argtypes = [ctypes.c_void_p]

        # The player GUID is the save folder name itself — use it as the key
        # directly instead of iterating, which is more robust across DLL versions.
        guid = save_dir.name.encode('ascii')
        val_len = ctypes.c_size_t()
        get_err = ctypes.c_char_p()

        val_ptr = lib.rocksdb_get_cf(
            db, ropts, cf_player,
            guid, len(guid),
            ctypes.byref(val_len), ctypes.byref(get_err)
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

        # Verify it looks like a BSON document
        if len(val_bytes) < 4 or struct.unpack_from('<I', val_bytes, 0)[0] != val_len.value:
            print(f"  [WARN] Data at key does not look like BSON ({val_len.value} bytes)")
            return None

        print(f"  Found player: {guid.decode()} ({val_len.value:,} bytes)")
        return guid, val_bytes

    except Exception as e:
        print(f"  [WARN] librocksdb read failed: {e}")
        return None

def write_wal(log_path: Path, seq: int, cf_id: int,
              player_key: bytes, bson_bytes: bytes):
    """
    Write a new WAL log file with the modified BSON payload.
    Handles RocksDB block fragmentation and CRC32C checksums.
    """
    # Build WriteBatch payload
    batch = (
        struct.pack('<Q', seq) +
        struct.pack('<I', 1) +       # count = 1 entry
        bytes([0x05]) +              # kTypeColumnFamilyValue
        write_varint(cf_id) +
        write_varint(len(player_key)) +
        player_key +
        write_varint(len(bson_bytes)) +
        bson_bytes
    )

    # Fragment into 32KB blocks with 7-byte record headers
    MAX_DATA = BLOCK_SIZE - 7
    fragments = []
    offset = 0
    total = len(batch)

    while offset < total:
        chunk = batch[offset:offset+MAX_DATA]
        offset += len(chunk)
        is_first = (offset - len(chunk) == 0)
        is_last  = (offset >= total)

        if is_first and is_last:
            rtype = 1   # FULL
        elif is_first:
            rtype = 2   # FIRST
        elif is_last:
            rtype = 4   # LAST
        else:
            rtype = 3   # MIDDLE

        crc_data = bytes([rtype]) + chunk
        crc = wal_masked_crc(crc_data)
        header = struct.pack('<I', crc) + struct.pack('<H', len(chunk)) + bytes([rtype])
        fragments.append(header + chunk)

    # Pad each fragment to block boundary
    output = b''
    for frag in fragments:
        output += frag
        pad = BLOCK_SIZE - (len(output) % BLOCK_SIZE)
        if pad < BLOCK_SIZE:
            output += b'\x00' * pad

    with open(log_path, 'wb') as f:
        f.write(output)

# ─────────────────────────────────────────────────────────────────────────────
#  Save data helpers
# ─────────────────────────────────────────────────────────────────────────────

def resolve_save_dir(save_dir: Path) -> Path:
    """
    Recursively search for the Players/<GUID> RocksDB folder.
    The actual save structure is:
      <SteamID>/RocksDB/<version>/Players/<PlayerGUID>/  ← we want this
    Falls back to any directory containing a CURRENT file.
    """
    # Already pointing at the right place
    if (save_dir / 'CURRENT').exists():
        return save_dir

    # Prefer a Players/<GUID> subdirectory anywhere in the tree
    for players_dir in save_dir.rglob('Players'):
        if players_dir.is_dir():
            candidates = [d for d in players_dir.iterdir()
                          if d.is_dir() and (d / 'CURRENT').exists()]
            if candidates:
                chosen = candidates[0]
                print(f"  [INFO] Auto-detected player save: ...\\Players\\{chosen.name}")
                return chosen

    # Fallback: any subdirectory containing CURRENT (up to 8 levels deep)
    for current_file in save_dir.rglob('CURRENT'):
        folder = current_file.parent
        if list(folder.glob('*.log')):   # must also have a WAL
            rel = folder.relative_to(save_dir)
            print(f"  [INFO] Found save at: {rel}")
            return folder

    return save_dir  # give up, let find_wal produce the real error


def find_wal(save_dir: Path) -> Path:
    logs = sorted(save_dir.glob('*.log'))
    if not logs:
        raise FileNotFoundError(
            f"No .log file found in: {save_dir}\n\n"
            f"  Point at the folder that contains CURRENT + *.sst + *.log,\n"
            f"  not a parent folder. Run:  dir \"{save_dir}\"  to see contents."
        )
    return logs[-1]

def new_item_guid() -> str:
    return uuid.uuid4().hex.upper()

def blank_item(item_params_path: str, level: int = 1, max_level: int = 15) -> dict:
    """Create a new item entry matching the game's save format.
    Equipment gets a level attribute; consumables/stackables get empty Attributes.
    """
    attrs = {}
    if is_equipment(item_params_path):
        attrs = {
            '0': {
                'MaxValue': max_level,
                'Tag': {'TagName': 'Inventory.Item.Attribute.Level'},
                'Value': max(1, level),
            }
        }
    return {
        'Attributes': attrs,
        'Effects': {},
        'ItemId': 'DB54628677934C810C9BCDDB309F1FE4',
        'ItemParams': item_params_path
    }

def infer_slot_params(mod: dict, slot_id: int) -> str:
    """
    Infer the correct SlotParams for a new slot by looking at existing
    slots in the same module. Falls back to DA_BL_Slot_Default.
    """
    slots = mod.get('Slots', {})
    for s in slots.values():
        sp = s.get('SlotParams', '')
        if sp:
            return sp
    return '/R5BusinessRules/Inventory/SlotsParams/DA_BL_Slot_Default.DA_BL_Slot_Default'


def blank_slot_with_item(item_params_path: str, level: int = 1,
                         count: int = 1, slot_id: int = 0,
                         mod: dict = None) -> dict:
    slot_params = (infer_slot_params(mod, slot_id)
                   if mod is not None
                   else '/R5BusinessRules/Inventory/SlotsParams/DA_BL_Slot_Default.DA_BL_Slot_Default')
    return {
        'IsPersonalSlot': False,
        'ItemsStack': {
            'Count': count,
            'Item': blank_item(item_params_path, level)
        },
        'SlotId': slot_id,
        'SlotParams': slot_params
    }

def get_all_items(doc: dict) -> list[dict]:
    """
    Returns a flat list of item records with context for display and editing.
    Each record: { path, module, slot, item_name, level, max_level, item_id, item_params }
    """
    items = []
    inventory = doc.get('Inventory', {})
    modules   = inventory.get('Modules', {})

    for mod_idx, mod in sorted(modules.items(), key=lambda x: int(x[0])):
        if not isinstance(mod, dict): continue
        slots = mod.get('Slots', {})
        if not isinstance(slots, dict): continue
        for slot_idx, slot in sorted(slots.items(), key=lambda x: int(x[0])):
            if not isinstance(slot, dict): continue
            stack = slot.get('ItemsStack', {})
            if not isinstance(stack, dict): continue
            item = stack.get('Item', {})
            if not isinstance(item, dict) or not item.get('ItemParams'): continue

            attrs    = item.get('Attributes', {})
            level    = None
            max_lvl  = None
            if isinstance(attrs, dict):
                for a in attrs.values():
                    if isinstance(a, dict) and 'Level' in a.get('Tag', {}).get('TagName', ''):
                        level   = a.get('Value')
                        max_lvl = a.get('MaxValue')
                        break

            params = item.get('ItemParams', '')
            name   = params.split('/')[-1].split('.')[0] if '/' in params else params

            items.append({
                'path':        f'Inventory.Modules.{mod_idx}.Slots.{slot_idx}',
                'module':      int(mod_idx),
                'slot':        int(slot_idx),
                'item_name':   name,
                'item_params': params,
                'item_id':     item.get('ItemId', ''),
                'level':       level,
                'max_level':   max_lvl,
                'count':       stack.get('Count', 1),
                'stack_ref':   stack,
                'mod_ref':     mod,
                'slot_ref':    slot,
                'item_ref':    item,
                'attrs_ref':   attrs,
            })
    return items

def get_module_capacity(mod: dict) -> int:
    """
    Return the total slot count for a module.
    Priority:
      1. Sum of CountSlots in AdditionalSlotsData (what the game stores)
      2. Highest used slot index + 1 (minimum lower bound)
      3. Default of 8 for completely empty modules
    """
    # AdditionalSlotsData holds the actual capacity grants
    total = 0
    for v in (mod.get('AdditionalSlotsData') or {}).values():
        if isinstance(v, dict):
            cs = v.get('CountSlots', 0)
            total += int(cs) if isinstance(cs, (int, BSONInt64)) else 0

    # ExtendCountSlots from backpack items
    ext = mod.get('ExtendCountSlots', 0)
    total += int(ext) if isinstance(ext, (int, BSONInt64)) else 0

    # Lower bound from highest occupied slot
    slots = mod.get('Slots') or {}
    if slots:
        max_used = max(int(k) for k in slots.keys())
        total = max(total, max_used + 1)

    return total if total > 0 else 8


def slot_has_item(slot: dict) -> bool:
    """Return True if this slot actually contains an item (non-empty ItemParams)."""
    params = slot.get('ItemsStack', {}).get('Item', {}).get('ItemParams', '')
    return bool(params)


def get_base_capacity(mod: dict) -> int:
    """
    Return the base (non-expansion) slot count for a module.
    These are the slots the game pre-allocates and manages itself.
    We derive this as the count of AdditionalSlotsData entries with the
    smallest CountSlots values — the base bag before any backpack expansion.
    Falls back to the total capacity if we can't determine it.
    """
    additional = mod.get('AdditionalSlotsData') or {}
    if not additional:
        return get_module_capacity(mod)
    # Sort slot grants by size — the first (smallest) is the base bag
    grants = sorted(
        (int(v.get('CountSlots', 0)) for v in additional.values() if isinstance(v, dict)),
    )
    return grants[0] if grants else get_module_capacity(mod)


def get_empty_slots(doc: dict, module: int = 0) -> list[int]:
    """
    Return slot indices safe for adding new items.
    Only returns expansion slots (index >= base capacity) to avoid
    conflicting with slots the game pre-allocates and manages itself.
    """
    mods     = doc.get('Inventory', {}).get('Modules', {})
    mod      = mods.get(str(module), {})
    slots    = mod.get('Slots', {})
    capacity = get_module_capacity(mod)
    base     = get_base_capacity(mod)
    empty = []
    for i in range(base, capacity):   # only look above base pre-allocated range
        slot = slots.get(str(i))
        if slot is None or not slot_has_item(slot):
            empty.append(i)
    return empty


# ── Talent / Skill name lookup ───────────────────────────────────────────────
# Built from StatsTree.csv exported alongside the locres

TALENT_NAMES = {
    "Talent_Crusher_Berserk": "Berserk",
    "Talent_Crusher_CrudeDamage": "Bonecrusher",
    "Talent_Crusher_DamageForDeathNearby": "Dominating Presence",
    "Talent_Crusher_DamageForMultipleTargets": "Momentum",
    "Talent_Crusher_DamageResistWithTwoHandedWpn": "Storm Bracing",
    "Talent_Crusher_TemporalHPHealBuff": "Retribution",
    "Talent_Crusher_TwoHandedDamage": "Massive",
    "Talent_Crusher_TwoHandedMeleeCritChance": "Executioner's Aim",
    "Talent_Crusher_TwoHandedStaminaReduced": "Perfected Form",
    "Talent_Fencer_ConsecutiveMeleeHitsBonus": "Deadly Finale",
    "Talent_Fencer_CritChanceForPerfectBlock": "Perfect Counter",
    "Talent_Fencer_DamageForSoloEnemy": "Duelist",
    "Talent_Fencer_HealForKill": "Executioner's Grace",
    "Talent_Fencer_LessStaminaForDash": "Agile",
    "Talent_Fencer_OneHandedDamage": "Quick Strikes",
    "Talent_Fencer_OneHandedMeleeCritChance": "Surgical Cuts",
    "Talent_Fencer_PassiveReloadBoostForPerfectBlock": "Disciplined Fencer",
    "Talent_Fencer_PassiveReloadBoostForPerfectDodge": "Evasive Fencer",
    "Talent_Fencer_RiposteDamageBonus": "Riposte Mastery",
    "Talent_Fencer_SlashDamage": "Deep Cuts",
    "Talent_Marksman_ActiveReloadSpeedBonus": "Quick Hand",
    "Talent_Marksman_ConsecutiveRangeHitsBonus": "Bulletstorm",
    "Talent_Marksman_DamageForAimingState": "Sniper's Focus",
    "Talent_Marksman_DamageForDistance": "Extended Reach",
    "Talent_Marksman_DamageForPointBlank": "Muzzle Reach",
    "Talent_Marksman_Overpenetration": "Overpenetration",
    "Talent_Marksman_PassiveReloadBonus": "Planning Ahead",
    "Talent_Marksman_PierceDamage": "Deep Impact",
    "Talent_Marksman_RangeCritDamageBonus": "Bull's Eye",
    "Talent_Marksman_RangeDamageBonus": "Firearm Training",
    "Talent_Marksman_ReloadForKill": "Deadly Hunter",
    "Talent_Toughguy_BlockPostureConsumptionBonus": "Flawless Defence",
    "Talent_Toughguy_DamageResistForHP": "Pain Tolerance",
    "Talent_Toughguy_DamageForManyEnemies": "Outnumbered",
    "Talent_Toughguy_ExtraHP": "Stout Frame",
    "Talent_Toughguy_HealEffectiveness": "Stitches and Rum",
    "Talent_Toughguy_MeleeDamageResist": "Just a Flesh Wound",
    "Talent_Toughguy_ResistForManyEnemies": "Outnumbered",
    "Talent_Toughguy_SaveOnLowHP": "Too Angry to Die",
    "Talent_Toughguy_StaminaBonus": "Marathon Runner",
    "Talent_Toughguy_TempHPForDamageRecivedBonus": "You Will Answer for This",
}

TALENT_DESCS = {
    "Talent_Crusher_Berserk": "For every X Health lost you gain a stack granting bonus Damage.",
    "Talent_Crusher_CrudeDamage": "Increases Crude Damage.",
    "Talent_Crusher_DamageForDeathNearby": "When an enemy dies nearby, gain Melee Damage bonus for a few seconds.",
    "Talent_Crusher_DamageForMultipleTargets": "Hitting multiple enemies grants stacking Damage bonus.",
    "Talent_Crusher_DamageResistWithTwoHandedWpn": "Gain Damage Resistance while wielding a two-handed weapon.",
    "Talent_Crusher_TemporalHPHealBuff": "Attacks are more effective at converting Temporal Health into Health.",
    "Talent_Crusher_TwoHandedDamage": "Increases two-handed weapon Damage.",
    "Talent_Crusher_TwoHandedMeleeCritChance": "Increases Critical Hit Chance with two-handed melee weapons.",
    "Talent_Crusher_TwoHandedStaminaReduced": "Two-handed weapon attacks consume less Stamina.",
    "Talent_Fencer_ConsecutiveMeleeHitsBonus": "Each consecutive hit increases Damage, capped after several hits.",
    "Talent_Fencer_CritChanceForPerfectBlock": "After a Perfect Block, Critical Hit Chance is increased briefly.",
    "Talent_Fencer_DamageForSoloEnemy": "When only one enemy is within 10m, melee attacks deal bonus Damage.",
    "Talent_Fencer_HealForKill": "On enemy kill, restore Health per tick for a few seconds.",
    "Talent_Fencer_LessStaminaForDash": "Dash and Jump consume less Stamina.",
    "Talent_Fencer_OneHandedDamage": "Increases one-handed weapon Damage.",
    "Talent_Fencer_OneHandedMeleeCritChance": "Increases Critical Hit Chance with one-handed melee weapons.",
    "Talent_Fencer_PassiveReloadBoostForPerfectBlock": "Perfect Blocks restore Passive Gun Reload progress.",
    "Talent_Fencer_PassiveReloadBoostForPerfectDodge": "Perfect Dashes restore Passive Gun Reload progress.",
    "Talent_Fencer_RiposteDamageBonus": "Increases Riposte Damage.",
    "Talent_Fencer_SlashDamage": "Increases Slash Damage.",
    "Talent_Marksman_ActiveReloadSpeedBonus": "Improves Active Reload Speed.",
    "Talent_Marksman_ConsecutiveRangeHitsBonus": "Consecutive ranged hits grant stacking Damage bonus to next shot.",
    "Talent_Marksman_DamageForAimingState": "While aiming, gain stacking Damage bonus over time.",
    "Talent_Marksman_DamageForDistance": "Shots deal bonus Damage per 10m between you and the target.",
    "Talent_Marksman_DamageForPointBlank": "Shots deal bonus Damage at close range (below 10m).",
    "Talent_Marksman_Overpenetration": "Shots penetrate enemies, dealing reduced damage after penetrating.",
    "Talent_Marksman_PassiveReloadBonus": "Improves Passive Gun Reload Speed.",
    "Talent_Marksman_PierceDamage": "Increases Pierce Damage.",
    "Talent_Marksman_RangeCritDamageBonus": "Hitting a critical spot deals bonus Damage.",
    "Talent_Marksman_RangeDamageBonus": "Increases Ranged Damage.",
    "Talent_Marksman_ReloadForKill": "Killing an enemy has a chance to instantly reload your weapon.",
    "Talent_Toughguy_BlockPostureConsumptionBonus": "Blocks consume less Posture Points.",
    "Talent_Toughguy_DamageResistForHP": "For every X Health lost, gain a stack granting Damage Resistance.",
    "Talent_Toughguy_DamageForManyEnemies": "When close to two or more enemies, gain Melee Damage bonus.",
    "Talent_Toughguy_ExtraHP": "Increases maximum Health.",
    "Talent_Toughguy_HealEffectiveness": "Gain increased effect from Healing.",
    "Talent_Toughguy_MeleeDamageResist": "Increases melee Damage Resistance.",
    "Talent_Toughguy_ResistForManyEnemies": "When close to two or more enemies, gain Damage Resistance.",
    "Talent_Toughguy_SaveOnLowHP": "When receiving a killing blow, instantly restore Health. Has a cooldown.",
    "Talent_Toughguy_StaminaBonus": "Grants additional Stamina.",
    "Talent_Toughguy_TempHPForDamageRecivedBonus": "Increases Temporal Health gain when taking damage.",
}

SKILL_CATEGORIES = {
    "Fencer":    {"label": "Fencer   (UP)",    "prefix": "DA_Talent_Fencer_"},
    "Toughguy":  {"label": "Toughguy (LEFT)",  "prefix": "DA_Talent_Toughguy_"},
    "Marksman":  {"label": "Marksman (DOWN)",  "prefix": "DA_Talent_Marksman_"},
    "Crusher":   {"label": "Crusher  (RIGHT)", "prefix": "DA_Talent_Crusher_"},
}

STAT_NAMES = {
    "DA_Strength_Stat":  "Strength",
    "DA_Agility_Stat":   "Agility",
    "DA_Precision_Stat": "Precision",
    "DA_Mastery_Stat":   "Mastery",
    "DA_Vitality_Stat":  "Vitality",
    "DA_Endurance_Stat": "Endurance",
}


def da_to_talent_key(da_path: str) -> str:
    """Convert DA asset path to talent name lookup key."""
    name = da_path.split('/')[-1].split('.')[0]
    if name.startswith('DA_'):
        name = name[3:]
    return name


def get_progression(doc: dict) -> dict:
    return doc.get('PlayerMetadata', {}).get('PlayerProgression', {})


def edit_stats(doc: dict) -> bool:
    """Stat editor — StatTree NodeLevel (0-60). NodeLevel lives on the node, not NodeData."""
    pp    = get_progression(doc)
    st    = pp.get('StatTree', {})
    nodes = st.get('Nodes', {})

    print(f"\n  === STAT EDITOR ===")
    print()

    stat_list = []
    for i, (k, v) in enumerate(sorted(nodes.items(), key=lambda x: int(x[0])), 1):
        nd       = v.get('NodeData', {})
        perks    = nd.get('Perks', {})
        perk_path = list(perks.values())[0] if perks else ''
        perk_name = perk_path.split('/')[-1].split('.')[0] if perk_path else f'Node{k}'
        real_name = STAT_NAMES.get(perk_name, perk_name)
        level     = v.get('NodeLevel', 0)       # NodeLevel is on the node itself
        max_lvl   = nd.get('MaxNodeLevel', 60)
        stat_list.append((k, v, nd, real_name, level, max_lvl))
        print(f"  {i}. {real_name:<14}  {level}/{max_lvl}")

    print()
    choice = input("  Stat # to edit (or Enter to go back): ").strip()
    if not choice:
        return False, None

    try:
        idx = int(choice) - 1
        k, v, nd, real_name, level, max_lvl = stat_list[idx]
    except (ValueError, IndexError):
        print("  Invalid choice.")
        input("  Press Enter…"); return False, None

    try:
        new_lvl = int(input(f"  New level for {real_name} (current: {level}, max: {max_lvl}): "))
        new_lvl = max(0, min(new_lvl, max_lvl))
        v['NodeLevel'] = new_lvl
        # Recalculate ProgressionPoints = sum of all node levels
        st['ProgressionPoints'] = sum(
            node.get('NodeLevel', 0) for node in nodes.values()
            if isinstance(node, dict)
        )
        print(f"  ✓ {real_name} → {new_lvl}/{max_lvl}")
        print(f"  ✓ ProgressionPoints updated → {st['ProgressionPoints']}")
        return True, f"Stat: {real_name} {level} -> {new_lvl}"
    except ValueError:
        print("  Invalid level.")
        input("  Press Enter..."); return False, None


def edit_skills(doc: dict) -> bool:
    """Skill editor — TalentTree NodeLevel (0-3), grouped by category."""
    pp = get_progression(doc)
    tt = pp.get('TalentTree', {})
    nodes = tt.get('Nodes', {})

    # Category selection loop
    while True:
        print(f"\n  === SKILL EDITOR ===")
        print()
        cats = list(SKILL_CATEGORIES.items())
        for i, (cat_key, cat_info) in enumerate(cats, 1):
            print(f"  {i}. {cat_info['label']}")
        print(f"  B. Back")
        print()

        cat_choice = input("  Category: ").strip().lower()
        if cat_choice == 'b':
            return False, None

        try:
            cat_key, cat_info = cats[int(cat_choice) - 1]
        except (ValueError, IndexError):
            print("  Invalid choice."); continue

        prefix = cat_info['prefix']

        # Collect nodes for this category
        cat_nodes = []
        for k, v in sorted(nodes.items(), key=lambda x: int(x[0])):
            nd    = v.get('NodeData', {})
            perks = nd.get('Perks', {})
            # Use NodeData.Perks to identify the skill — ActivePerk is empty when level=0
            perk_path = list(perks.values())[0] if perks else ''
            perk_asset = perk_path.split('/')[-1].split('.')[0] if perk_path else ''
            if cat_key not in perk_asset:
                continue
            talent_key = da_to_talent_key(perk_path) if perk_path else ''
            fallback   = perk_asset.replace('DA_Talent_' + cat_key + '_', '') if perk_asset else f'Node {k}'
            real_name  = TALENT_NAMES.get(talent_key, fallback)
            level      = v.get('NodeLevel', 0)
            max_lvl    = nd.get('MaxNodeLevel', 3)
            cat_nodes.append((k, v, nd, real_name, talent_key, level, max_lvl))

        if not cat_nodes:
            print(f"  No {cat_key} skills found (may not be unlocked yet).")
            input("  Press Enter…"); continue

        show_descs = False
        while True:
            print(f"\n  {cat_info['label']} Skills")
            print(f"  {'#':<4} {'Name':<30} {'Level'}")
            print("  " + "─" * 45)
            for i, (k, v, nd, real_name, talent_key, level, max_lvl) in enumerate(cat_nodes):
                print(f"  {i:<4} {real_name:<30} {level}/{max_lvl}")
                if show_descs and talent_key in TALENT_DESCS:
                    print(f"       {TALENT_DESCS[talent_key]}")

            print()
            print("  D. Toggle descriptions  |  B. Back to categories")
            print()
            skill_choice = input("  Skill # to edit: ").strip().lower()

            if skill_choice == 'b':
                break
            if skill_choice == 'd':
                show_descs = not show_descs
                continue
            try:
                si = int(skill_choice)
                k, v, nd, real_name, talent_key, level, max_lvl = cat_nodes[si]
            except (ValueError, IndexError):
                print("  Invalid choice."); continue

            try:
                new_lvl = int(input(f"  New level for {real_name} (current: {level}, max: {max_lvl}): "))
                new_lvl = max(0, min(new_lvl, max_lvl))
                v['NodeLevel'] = new_lvl
                # Recalculate ProgressionPoints = sum of all node levels
                tt['ProgressionPoints'] = sum(
                    node.get('NodeLevel', 0) for node in nodes.values()
                    if isinstance(node, dict)
                )
                # Update local cache
                cat_nodes[si] = (k, v, nd, real_name, talent_key, new_lvl, max_lvl)
                print(f"  ✓ {real_name} → {new_lvl}/{max_lvl}")
                print(f"  ✓ ProgressionPoints updated → {tt['ProgressionPoints']}")
                return True, f"Skill: {real_name} {level} -> {new_lvl}"
            except ValueError:
                print("  Invalid level.")

    return False, None



# ── Item type detection ────────────────────────────────────────────────────
WEAPON_PREFIXES = ('DA_EID_MeleeWeapon_', 'DA_EID_RangeWeapon_', 'DA_EID_Weapon_')
ARMOR_PREFIXES  = ('DA_EID_Armor_', 'DA_EID_Helmet_', 'DA_EID_Gloves_',
                   'DA_EID_Boots_', 'DA_EID_Legs_', 'DA_EID_Chest_')
EQUIP_PREFIXES  = WEAPON_PREFIXES + ARMOR_PREFIXES

def is_equipment(item_params: str) -> bool:
    """Return True if the ItemParams path is a weapon or armor."""
    name = item_params.split('/')[-1].split('.')[0]
    return any(name.startswith(p) for p in EQUIP_PREFIXES)

def ensure_equipment_integrity(item: dict, stack: dict,
                               old_params: str, new_params: str):
    """
    Enforce item rules when replacing:
    - New item is weapon/armor: Count=1, Level>=1, add attr if missing
    - New item is NOT equipment (was weapon/armor): Level=0
    """
    was_equip = is_equipment(old_params)
    now_equip = is_equipment(new_params)

    if now_equip:
        stack['Count'] = 1
        attrs = item.get('Attributes', {})
        level_attr = None
        for a in attrs.values():
            if isinstance(a, dict) and 'Level' in a.get('Tag', {}).get('TagName', ''):
                level_attr = a
                break
        if level_attr is None:
            item.setdefault('Attributes', {})['0'] = {
                'MaxValue': 15,
                'Tag': {'TagName': 'Inventory.Item.Attribute.Level'},
                'Value': 1
            }
            print("  [Auto] Added missing level attribute (set to 1)")
        elif level_attr.get('Value', 0) < 1:
            level_attr['Value'] = 1
            print("  [Auto] Level was 0 - set to 1 (minimum for equipment)")
    elif was_equip and not now_equip:
        attrs = item.get('Attributes', {})
        for a in attrs.values():
            if isinstance(a, dict) and 'Level' in a.get('Tag', {}).get('TagName', ''):
                a['Value'] = 0
                print("  [Auto] Level reset to 0 (non-equipment item)")
                break


# ─────────────────────────────────────────────────────────────────────────────
#  CLI interface
# ─────────────────────────────────────────────────────────────────────────────

def print_header():
    print("\n" + "═"*70)
    print("  WINDROSE SAVE EDITOR")
    print("═"*70)

def print_inventory(items: list[dict]):
    print(f"\n{'#':<4} {'Module':<8} {'Slot':<6} {'Lvl':<6} {'Cnt':<5} Item")
    print("─"*70)
    for i, it in enumerate(items):
        lvl = f"{it['level']}/{it['max_level']}" if it['level'] is not None else "—"
        cnt = it['count'] if it['count'] > 1 else ""
        name = it['item_name']
        if len(name) > 45: name = name[:43] + "…"
        print(f"{i:<4} {it['module']:<8} {it['slot']:<6} {lvl:<6} {str(cnt):<5} {name}")


def list_backups(save_dir: Path) -> list[Path]:
    """Find backups — checks Steam root level (all DBs) and Players level."""
    backups = []
    root = find_save_root(save_dir)
    # Full-root backups (preferred)
    for d in root.parent.iterdir():
        if d.is_dir() and d.name.startswith(root.name + '_backup_'):
            backups.append(d)
    # Old Players-only backups
    for d in save_dir.parent.iterdir():
        if d.is_dir() and d.name.startswith(save_dir.name + '_backup_'):
            backups.append(d)
    return sorted(set(backups), key=lambda d: d.name, reverse=True)


def restore_backup(save_dir: Path) -> bool:
    backups = list_backups(save_dir)
    if not backups:
        print("  No backups found.")
        return False, None

    root = find_save_root(save_dir)
    print()
    print("  Available backups (newest first):")
    for i, b in enumerate(backups):
        is_full = b.name.startswith(root.name + '_backup_')
        tag = "[full]" if is_full else "[players only]"
        ts  = b.name.split('_backup_')[-1]
        print(f"    {i}) {ts}  {tag}")
    print()

    try:
        idx    = int(input("  Which backup to restore? (number): "))
        chosen = backups[idx]
    except (ValueError, IndexError):
        print("  Cancelled.")
        return False, None

    is_root_backup = chosen.name.startswith(root.name + '_backup_')
    restore_target = root if is_root_backup else save_dir

    broken_path = restore_target.parent / (restore_target.name + '_broken')
    if broken_path.exists():
        shutil.rmtree(broken_path)
    restore_target.rename(broken_path)
    chosen.rename(restore_target)

    scope = "full save (Accounts + Players + Worlds)" if is_root_backup else "Players only"
    print(f"  ✓ Restored {scope}: {chosen.name}")
    print(f"  ✓ Old save kept as: {broken_path.name}")
    print()
    print("  Launch game to verify, then re-run editor to make your edits.")
    return True


def kill_game() -> bool:
    """
    Force-kill the game process. Returns True if a process was killed.
    Requires: pip install psutil
    """
    try:
        import psutil
    except ImportError:
        print("  [INFO] psutil not installed — can't auto-close game.")
        print("         Run:  pip install psutil  to enable this feature.")
        return False, None

    killed = []
    for proc in psutil.process_iter(['name', 'pid']):
        try:
            if proc.info['name'] in GAME_PROCESS_NAMES:
                proc.kill()
                killed.append(proc.info['name'])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    if killed:
        import time
        print(f"  ✓ Killed: {', '.join(killed)}")
        print("  Waiting for process to exit…", end=' ', flush=True)
        time.sleep(2)   # brief pause so RocksDB releases file handles
        print("done")
        return True
    else:
        print("  Game doesn't appear to be running.")
        return False, None


def find_save_root(save_dir: Path) -> Path:
    """
    Find the Steam ID root folder that contains ALL databases (Players, Worlds, Accounts).
    save_dir is .../76561197960287777/RocksDB/0.10.0/Players/<GUID>
    We walk up until we find a folder that looks like a Steam ID (numeric name).
    """
    path = save_dir
    for _ in range(8):
        path = path.parent
        if path.name.isdigit() and len(path.name) >= 10:
            return path
    # Fallback: return the Players GUID folder (old behaviour)
    return save_dir


def save_backup(save_dir: Path):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Back up the entire Steam ID folder so Accounts + Players + Worlds
    # are all captured together at the same point in time.
    root = find_save_root(save_dir)
    backup = root.parent / f"{root.name}_backup_{ts}"

    print(f"  Backing up full save root: {root.name}  (Accounts + Players + Worlds)…")
    shutil.copytree(root, backup, ignore=shutil.ignore_patterns('LOCK'))
    print(f"✓ Backup saved: {backup}")
    return backup

def parse_manifest(save_dir: Path) -> tuple[int, int, int]:
    """
    Parse the RocksDB MANIFEST to get:
      last_sequence, next_file_number, log_number
    These are needed to write a valid WAL that the game will replay.
    """
    manifests = sorted(save_dir.glob('MANIFEST-*'))
    if not manifests:
        return 0, 0, 0
    raw = manifests[-1].read_bytes()

    last_sequence    = 0
    next_file_number = 0
    log_number       = 0

    pos = 0
    while pos < len(raw):
        if pos + 7 > len(raw): break
        length = struct.unpack_from('<H', raw, pos+4)[0]
        chunk  = raw[pos+7:pos+7+length]
        pos   += 7 + length
        rem = pos % 32768
        if 0 < rem < 7:
            pos += 32768 - rem

        p = 0
        while p < len(chunk):
            try:
                tag, np = read_varint(chunk, p)
                if tag == 2:
                    v, np = read_varint(chunk, np)
                    log_number = max(log_number, v)
                elif tag == 3:
                    v, np = read_varint(chunk, np)
                    next_file_number = max(next_file_number, v)
                elif tag == 4:
                    v, np = read_varint(chunk, np)
                    last_sequence = max(last_sequence, v)
                p += 1
            except:
                p += 1

    return last_sequence, next_file_number, log_number


def append_manifest_record(save_dir: Path, new_log_number: int,
                            new_last_sequence: int, new_next_file: int):
    """Append a VersionEdit record to the MANIFEST so RocksDB replays our WAL."""
    manifests = sorted(save_dir.glob('MANIFEST-*'))
    if not manifests:
        return

    body = (
        write_varint(2) + write_varint(new_log_number) +
        write_varint(3) + write_varint(new_next_file) +
        write_varint(4) + write_varint(new_last_sequence)
    )
    crc_data = bytes([1]) + body   # type=1 FULL record
    crc      = wal_masked_crc(crc_data)
    record   = struct.pack('<IHB', crc, len(body), 1) + body

    with open(manifests[-1], 'ab') as f:
        f.write(record)


def verify_wal(wal_path: Path, expected_key: bytes) -> bool:
    """Read back the WAL we just wrote and confirm it parses correctly."""
    try:
        result = read_wal(wal_path)
        if result is None:
            print(f"  [VERIFY] FAIL — WAL reads as empty")
            return False, None
        seq, cf, key, bson, _ = result
        if key != expected_key:
            print(f"  [VERIFY] FAIL — key mismatch: {key} vs {expected_key}")
            return False, None
        doc = parse_bson(bson)
        if not doc.get('_guid'):
            print(f"  [VERIFY] FAIL — BSON missing _guid")
            return False, None
        print(f"  [VERIFY] OK — seq={seq} key={key.decode()} bson={len(bson):,}B")
        return True
    except Exception as e:
        print(f"  [VERIFY] FAIL — {e}")
        return False, None


def write_via_rocksdb(save_dir: Path, cf_id: int,
                      player_key: bytes, bson_bytes: bytes) -> bool:
    """
    Write the modified BSON into the existing empty WAL file that the game
    created on its last normal close, using the correct sequence number from
    the MANIFEST so RocksDB replays it without complaint.
    """
    # Get the current WAL file number and MANIFEST sequence
    log_files = sorted(save_dir.glob('*.log'),
                       key=lambda f: int(f.stem) if f.stem.isdigit() else 0)
    if not log_files:
        print("  [ERROR] No .log file found in save directory.")
        return False, None

    last_sequence, next_file_number, log_number = parse_manifest(save_dir)
    if last_sequence == 0:
        print("  [WARN] Could not read last_sequence from MANIFEST")
        last_sequence = 50000
    write_seq = last_sequence + 1

    # Write to a NEW file number (current + 1) with the correct sequence.
    # Writing to the EXISTING WAL causes infinite loading because RocksDB
    # considers its data already applied (flushed to SST on normal close).
    # A new file with number > log_number is scanned and replayed on startup.
    # Do NOT update the MANIFEST — RocksDB scans for all .log files >= log_number
    # automatically, so our new file will be found and replayed.
    current_num = int(log_files[-1].stem)
    new_wal_path = save_dir / f"{current_num + 1:06d}.log"

    print(f"  MANIFEST: last_seq={last_sequence}  log_num={log_number}")
    print(f"  Writing new WAL: {new_wal_path.name}  seq={write_seq}")

    write_wal(new_wal_path, write_seq, cf_id, player_key, bson_bytes)

    print(f"  Verifying WAL readback…", end=' ')
    if not verify_wal(new_wal_path, player_key):
        print("  WAL write may be corrupted.")
        return False, None

    print(f"✓ WAL verified and ready")
    return True


def _wait_for_game_exit():
    """
    Ask the user to quit the game normally (via in-game menu), then wait
    until all game processes are gone. A normal quit flushes all databases
    cleanly, preventing partial WAL writes that cause infinite loading.
    """
    try:
        import psutil
    except ImportError:
        input("  Close the game completely, then press Enter…")
        return

    # Check if any game process is still running
    def game_running():
        for p in psutil.process_iter(['name']):
            try:
                if p.info['name'] in GAME_PROCESS_NAMES:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return False

    if not game_running():
        return   # already closed — proceed immediately

    print()
    print("  ┌──────────────────────────────────────────────────────────┐")
    print("  │  QUIT THE GAME NOW via the in-game menu (Esc → Quit).   │")
    print("  │  Do NOT Alt+F4 or use Task Manager.                      │")
    print("  │  The editor will write your changes once it's closed.    │")
    print("  └──────────────────────────────────────────────────────────┘")
    print()
    print("  Waiting for game to close… (press S to skip if already closed)")
    print("  ", end='', flush=True)

    import time, threading, sys, msvcrt

    skip = threading.Event()
    def watch_key():
        while not skip.is_set():
            if msvcrt.kbhit():
                ch = msvcrt.getch().lower()
                if ch == b's':
                    skip.set()
            time.sleep(0.05)

    watcher = threading.Thread(target=watch_key, daemon=True)
    watcher.start()

    while not skip.is_set() and game_running():
        time.sleep(1)
        print('.', end='', flush=True)

    skip.set()
    if not game_running():
        time.sleep(2)
        print(" closed!")
    else:
        print(" skipped.")
    print()


def commit_changes(save_dir: Path, wal_path: Path,
                   seq: int, cf_id: int, player_key: bytes,
                   doc: dict, bson_bytes: bytes,
                   batch_count: int = 1, modified: bool = False) -> bool:
    """
    Serialize the modified doc and write it as a NEW WAL file.
    The existing WAL is left untouched so other column family data
    (ship, buildings, etc.) is not lost.  Our new file has a higher
    log number and sequence, so RocksDB replays it last and our
    player changes win.
    """
    print("\nSerializing BSON…", end=' ', flush=True)
    new_bson = serialize_bson_doc(doc)
    print(f"{len(new_bson):,} bytes")

    # Byte-level check only applies to unmodified saves (serialiser regression test).
    # When the user made changes the BSON will intentionally differ — skip the check.
    if not modified:
        if new_bson != bson_bytes:
            diffs = sum(1 for a, b in zip(new_bson, bson_bytes) if a != b)
            first = next(i for i,(a,b) in enumerate(zip(new_bson,bson_bytes)) if a!=b)
            print(f"\n[ERROR] BSON is not byte-perfect (no changes were made but output differs)!")
            print(f"  {diffs} differing bytes, first at offset {first}")
            print(f"  Original byte: 0x{bson_bytes[first]:02x}")
            print(f"  New byte:      0x{new_bson[first]:02x}")
            print(f"  Context orig:  {bson_bytes[max(0,first-4):first+8].hex()}")
            print(f"  Context new:   {new_bson[max(0,first-4):first+8].hex()}")
            print("\nSave aborted — your backup is safe.")
            return False
        print("✓ BSON byte-perfect round-trip verified")
    else:
        print("✓ BSON serialized with changes")

    _wait_for_game_exit()

    # Write directly via the RocksDB C API — no WAL crafting, no MANIFEST
    # timing issues. RocksDB handles all internal bookkeeping automatically.
    print("Writing to database…", end=' ', flush=True)
    ok = write_via_rocksdb(save_dir, cf_id, player_key, new_bson)
    if ok:
        print("done")
        print(f"✓ Written via RocksDB API directly into SST/WAL")
        return True

    # WAL fallback removed — manual WAL writing causes infinite loading
    # because the MANIFEST min_log_number may be ahead of our file.
    print()
    print("  [ERROR] RocksDB direct write failed. Your backup is safe.")
    print("  Restore it via option 9 if needed.")
    return False

def peek_player_name(player_dir: Path) -> str:
    """Read player name from the WAL or SST without full parse."""
    try:
        wal_path = find_wal(player_dir)
        result = read_wal(wal_path)
        if result:
            _, _, _, bson_bytes, _ = result
            doc = parse_bson(bson_bytes)
            return doc.get('PlayerName', '')
    except Exception:
        pass
    # Try SST via rocksdb
    try:
        result = scan_sst_for_player(player_dir)
        if result:
            _, bson_bytes = result
            doc = parse_bson(bson_bytes)
            return doc.get('PlayerName', '')
    except Exception:
        pass
    return ''


def pick_save_interactively() -> Path | None:
    """
    Auto-detect save location and let the user pick Steam ID + character.
    Returns the resolved Players/<GUID> path or None if cancelled.
    """
    import os

    local_app = Path(os.environ.get('LOCALAPPDATA', ''))
    profiles_root = local_app / 'R5' / 'Saved' / 'SaveProfiles'

    if not profiles_root.exists():
        print(f"[ERROR] Could not find save profiles at: {profiles_root}")
        print("  Run with a path argument: python windrose_save_editor.py <path>")
        return None

    # Find all Steam ID folders (numeric names, not backups)
    steam_ids = sorted([
        d for d in profiles_root.iterdir()
        if d.is_dir() and d.name.isdigit()
    ])

    if not steam_ids:
        print(f"[ERROR] No Steam ID folders found in {profiles_root}")
        return None

    # Pick Steam ID
    if len(steam_ids) == 1:
        steam_dir = steam_ids[0]
        print(f"  Steam ID: {steam_dir.name}")
    else:
        print("\n  Steam accounts found:")
        for i, d in enumerate(steam_ids, 1):
            print(f"    {i}. {d.name}")
        print()
        try:
            choice = int(input("  Select account: ")) - 1
            steam_dir = steam_ids[choice]
        except (ValueError, IndexError):
            print("  Cancelled.")
            return None

    # Find Players directory
    players_root = steam_dir / 'RocksDB' / '0.10.0' / 'Players'
    if not players_root.exists():
        print(f"[ERROR] Players folder not found: {players_root}")
        return None

    player_dirs = sorted([
        d for d in players_root.iterdir()
        if d.is_dir() and (d / 'CURRENT').exists()
    ])

    if not player_dirs:
        print("[ERROR] No player saves found.")
        return None

    if len(player_dirs) == 1:
        return player_dirs[0]

    # Multiple characters — fetch names
    print("\n  Characters found:")
    entries = []
    for d in player_dirs:
        print(f"    Loading {d.name}...", end='\r', flush=True)
        name = peek_player_name(d)
        entries.append((d, name))
        label = f"{d.name}  |  {name}" if name else d.name
        print(f"    {len(entries)}. {label}          ")

    print()
    try:
        choice = int(input("  Select character: ")) - 1
        return entries[choice][0]
    except (ValueError, IndexError):
        print("  Cancelled.")
        return None


def main():
    if len(sys.argv) >= 2:
        save_dir = Path(sys.argv[1]).resolve()
        if not save_dir.exists():
            print(f"[ERROR] Directory not found: {save_dir}")
            sys.exit(1)
        save_dir = resolve_save_dir(save_dir)
    else:
        save_dir = pick_save_interactively()
        if save_dir is None:
            print("No save selected.")
            sys.exit(0)

    if not (save_dir / 'CURRENT').exists():
        print(f"[ERROR] Could not find a save folder (no CURRENT file) under:")
        print(f"        {Path(sys.argv[1]).resolve()}")
        print(f"\n  Run:  dir \"{Path(sys.argv[1]).resolve()}\"  to see what's inside.")
        sys.exit(1)

    wal_path = find_wal(save_dir)
    print(f"\nReading: {wal_path.name}")

    result = read_wal(wal_path)
    cf_id = 2
    player_key = None

    if result is not None:
        seq, cf_id, player_key, bson_bytes, last_batch_count = result
        print()
        print()
        print("  ⚠  Game is RUNNING — player data read from live WAL.")
        print()
        print("  Make your edits, then use option 6 to save.")
        print("  The editor will guide you through closing the game safely.")
        print()
    else:
        print("  WAL is empty — data has been compacted into SST files.")
        print("  Scanning SST files for player data…")
        sst_result = scan_sst_for_player(save_dir)
        if sst_result is None:
            print("[ERROR] Could not find player data in WAL or SST files.")
            sys.exit(1)
        player_key, bson_bytes = sst_result
        seq = 99999
        last_batch_count = 1

    doc = parse_bson(bson_bytes)

    print(f"Player:   {doc.get('PlayerName', '?')}")
    print(f"GUID:     {doc.get('_guid', '?')}")
    print(f"Version:  {doc.get('_version', '?')}")
    print(f"WAL seq:  {seq}")

    # Track whether we've backed up
    backed_up = False
    modified  = False
    changelog = []

    while True:
        print_header()
        print(f"  Player: {doc.get('PlayerName', '?')}  |  Save: {save_dir.name}")
        print(f"  1. View inventory")
        print(f"  2. Set Item Level")
        print(f"  3. Set Item Count")
        print(f"  4. Replace Item")
        print(f"  5. Stat Editor")
        print(f"  6. Skill Editor")
        print(f"  7. Export full save as JSON")
        print(f"  8. Force-close game")
        print(f"  9. Save changes")
        print(f"  A. Restore a backup")
        print(f"  0. Quit (unsaved changes will be lost)")
        print(f"")
        print(f"  DEV. Experimental (Do not use)")
        print()

        choice = input("  Choice: ").strip().lower()

        if choice == '1':
            items = get_all_items(doc)
            if not items:
                print("  No items found in inventory.")
            else:
                print_inventory(items)
            input("\n  Press Enter to continue…")

        elif choice == '2':
            items = get_all_items(doc)
            print_inventory(items)
            try:
                idx = int(input("\n  Item # to change level: "))
                it  = items[idx]
                if it['level'] is None:
                    print(f"  '{it['item_name']}' has no level attribute.")
                    input("  Press Enter…"); continue
                new_lvl = int(input(f"  New level (current: {it['level']}, max: {it['max_level']}): "))
                # Find and update the attribute
                attrs = it['attrs_ref']
                for a in attrs.values():
                    if isinstance(a, dict) and 'Level' in a.get('Tag', {}).get('TagName', ''):
                        a['Value'] = new_lvl
                        break
                print(f"  ✓ {it['item_name']} → level {new_lvl}")
                changelog.append(f"Level:   {it['item_name']} {it['level']} -> {new_lvl}")
                modified = True
            except (ValueError, IndexError) as e:
                print(f"  Invalid input: {e}")
            input("  Press Enter…")

        elif choice == '3':
            items = get_all_items(doc)
            print_inventory(items)
            try:
                idx     = int(input("\n  Item # to change count: "))
                it      = items[idx]
                new_cnt = int(input(f"  New count (current: {it['count']}): "))
                it['stack_ref']['Count'] = new_cnt
                print(f"  ✓ {it['item_name']} → count {new_cnt}")
                changelog.append(f"Count:   {it['item_name']} {it['count']} -> {new_cnt}")
                modified = True
            except (ValueError, IndexError) as e:
                print(f"  Invalid input: {e}")
            input("  Press Enter…")

        elif choice == '4':
            items = get_all_items(doc)
            print_inventory(items)
            print()
            print("  Replace an item by swapping its ItemParams.")
            print("  The slot, level, count and slot structure stay identical.")
            print("  Example: replace Green Rapier with Blue/Purple variant.")
            print()
            try:
                idx = int(input("  Item # to replace: "))
                it  = items[idx]
            except (ValueError, IndexError):
                print("  Invalid item number.")
                input("  Press Enter…"); continue

            print(f"  Current: {it['item_name']}")
            print(f"  Current ItemParams: {it['item_params']}")
            print()
            new_params = input("  New ItemParams: ").strip()
            if not new_params:
                print("  Cancelled.")
                input("  Press Enter…"); continue

            # Auto-fix common copy-paste issues
            if new_params and not new_params.startswith('/'):
                new_params = '/' + new_params
            # Strip Plugins/Content if pasted from old HTML
            if new_params.startswith('/Plugins/'):
                new_params = new_params[len('/Plugins/'):]
            new_params = new_params.replace('/Content/', '/')

            # Update ItemParams and generate a fresh ItemId
            it['item_ref']['ItemParams'] = new_params
            it['item_ref']['ItemId']     = new_item_guid()

            # Only prompt for level when BOTH old and new are equipment (weapon->weapon)
            # food->weapon: integrity auto-sets to 1, no prompt needed
            # weapon->food: integrity auto-sets to 0, no prompt needed
            if is_equipment(new_params) and is_equipment(it['item_params']):
                new_level_str = input(f"  New level (Enter to keep {it['level']}): ").strip()
                if new_level_str:
                    try:
                        new_level = int(new_level_str)
                        for a in it['attrs_ref'].values():
                            if isinstance(a, dict) and 'Level' in a.get('Tag',{}).get('TagName',''):
                                a['Value'] = new_level
                                break
                    except ValueError:
                        pass

            # Enforce weapon/armor integrity rules (handles both directions)
            ensure_equipment_integrity(it['item_ref'], it['stack_ref'], it['item_params'], new_params)

            # If going from equipment -> stackable, offer to set quantity
            if is_equipment(it['item_params']) and not is_equipment(new_params):
                qty_str = input("  Set quantity (Enter to keep 1): ").strip()
                if qty_str:
                    try:
                        qty = max(1, int(qty_str))
                        it['stack_ref']['Count'] = qty
                        changelog.append(f"Count:   {new_name} set to {qty}")
                    except ValueError:
                        pass

            new_name = new_params.split('/')[-1].split('.')[0]
            print(f"  ✓ Replaced with: {new_name}")
            changelog.append(f"Replace: {it['item_name']} -> {new_name}")
            modified = True
            input("  Press Enter…")

        elif choice == '5':
            result = edit_stats(doc)
            ok, msg = result if isinstance(result, tuple) else (result, None)
            if ok:
                modified = True
                if msg: changelog.append(msg)
            input('  Press Enter...')

        elif choice == '6':
            result = edit_skills(doc)
            ok, msg = result if isinstance(result, tuple) else (result, None)
            if ok:
                modified = True
                if msg: changelog.append(msg)

        elif choice == 'dev':
            print("\n  ⚠  EXPERIMENTAL — Use at your own risk")
            print("  1. Add item to inventory")
            print("  2. Remove item from inventory")
            print("  B. Back")
            print()
            dev_choice = input("  Choice: ").strip().lower()
            if dev_choice == '1':
                choice = '_add'
            elif dev_choice == '2':
                choice = '_remove'
            else:
                input("  Press Enter…"); continue

        if choice == '_add':
            print("\n  Enter the ItemParams path for the item to add.")
            print("  Example: /R5BusinessRules/InventoryItems/Equipments/Armor/DA_EID_Armor_Flibustier_Base_Torso.DA_EID_Armor_Flibustier_Base_Torso")
            print("  (This is shown in the Item ID Guide when you click an item)")
            print()
            params = input("  ItemParams: ").strip()
            if not params:
                input("  Cancelled. Press Enter…"); continue

            # Auto-fix common copy-paste issues
            if params and not params.startswith('/'):
                params = '/' + params
            if params.startswith('/Plugins/'):
                params = params[len('/Plugins/'):]
            params = params.replace('/Content/', '/')

            # Show module capacities to help the user pick
            mods = doc.get('Inventory', {}).get('Modules', {})
            print()
            print("  Module     Used / Capacity   Free slots")
            for m_idx in sorted(mods.keys(), key=lambda x: int(x)):
                m     = mods[m_idx]
                slots = m.get('Slots', {})
                cap   = get_module_capacity(m)
                used  = sum(1 for s in slots.values() if slot_has_item(s))
                free  = cap - used
                print(f"    {m_idx:<10} {used:>4} / {cap:<6}   {'✓ ' + str(free) + ' free' if free > 0 else '— full'}")
            print()

            try:
                mod_idx  = int(input("  Module index: "))
                level    = int(input("  Level (1–15, or 0 if not applicable): "))
                count    = int(input("  Count (1 for equipment, more for stackables): "))
            except ValueError:
                print("  Invalid input.")
                input("  Press Enter…"); continue

            empty = get_empty_slots(doc, mod_idx)
            if not empty:
                print(f"  Module {mod_idx} is full ({get_module_capacity(mods.get(str(mod_idx), {}))}/{get_module_capacity(mods.get(str(mod_idx), {}))}).")
                print("  Pick a different module or remove an item first.")
                input("  Press Enter…"); continue

            slot_idx = empty[0]
            mods = doc['Inventory']['Modules']
            if str(mod_idx) not in mods:
                print(f"  Module {mod_idx} not found.")
                input("  Press Enter…"); continue

            slots = mods[str(mod_idx)].setdefault('Slots', {})
            # If the slot already exists (pre-allocated empty), patch it in place
            existing = slots.get(str(slot_idx))
            new_item = blank_item(params, level)
            if existing is not None:
                stack = existing.setdefault('ItemsStack', {})
                stack['Count'] = count
                stack['Item'] = new_item
                existing['SlotId'] = slot_idx
            else:
                slots[str(slot_idx)] = blank_slot_with_item(params, level, count, slot_idx, mod=mods[str(mod_idx)])

            # Register in WasTouchedItems so the game recognises the item instance
            inv_meta = doc.setdefault('PlayerMetadata', {}).setdefault('InventoryMetadata', {})
            touched  = inv_meta.setdefault('WasTouchedItems', {})
            next_key = str(max((int(k) for k in touched.keys()), default=-1) + 1)
            touched[next_key] = {
                'Item': {
                    'Attributes': new_item.get('Attributes', {}),
                    'Effects':    {},
                    'ItemId':     new_item['ItemId'],
                    'ItemParams': params,
                },
                'bIsNew': False,
            }

            name = params.split('/')[-1].split('.')[0]
            print(f"  ✓ Added '{name}' to module {mod_idx} slot {slot_idx}")
            modified = True
            input("  Press Enter…")

        elif choice == '_remove':
            items = get_all_items(doc)
            print_inventory(items)
            try:
                idx = int(input("\n  Item # to REMOVE: "))
                it  = items[idx]
                confirm = input(f"  Remove '{it['item_name']}'? [y/N] ").strip().lower()
                if confirm == 'y':
                    mods  = doc['Inventory']['Modules']
                    slots = mods[str(it['module'])]['Slots']
                    del slots[str(it['slot'])]
                    print(f"  ✓ Removed '{it['item_name']}'")
                    modified = True
            except (ValueError, IndexError) as e:
                print(f"  Invalid input: {e}")
            input("  Press Enter…")

        elif choice == '9':
            if not modified:
                print("  No changes to save.")
                input("  Press Enter..."); continue

            print()
            print("  Changes this session:")
            print("  " + "-"*60)
            for entry in changelog:
                print(f"    {entry}")
            if not changelog:
                print("    (no tracked changes)")
            print("  " + "-"*60)
            print()
            confirm_save = input("  Save these changes? [Y/n]: ").strip().lower()
            if confirm_save not in ('', 'y', 'yes'):
                print("  Save cancelled.")
                input("  Press Enter..."); continue

            if not backed_up:
                print()
                bk = save_backup(save_dir)
                backed_up = True

            try:
                ok = commit_changes(save_dir, wal_path, seq, cf_id, player_key,
                                    doc, bson_bytes, last_batch_count, modified)
                if ok:
                    modified = False
                    print("  ✓ Changes written. Launch the game to verify.")
            except Exception as e:
                import traceback
                print(f"  [ERROR] Save failed: {e}")
                traceback.print_exc()
            input("  Press Enter…")

        elif choice == '7':
            out = save_dir.parent / f"{save_dir.name}_dump_{datetime.now().strftime('%H%M%S')}.json"
            with open(out, 'w', encoding='utf-8') as f:
                json.dump(doc, f, indent=2, ensure_ascii=False, default=str)
            print(f"  ✓ Exported: {out}")
            input("  Press Enter…")


        elif choice == '8':
            kill_game()
            input('  Press Enter...')

        elif choice == 'a':
            confirm = input('  Replace current save with a backup? [y/N]: ').strip().lower()
            if confirm == 'y':
                if restore_backup(save_dir):
                    print('  Exiting - relaunch editor after verifying.')
                    break
            input('  Press Enter...')


        elif choice == '0':
            if modified:
                confirm = input('  Unsaved changes will be lost. Quit anyway? [y/N] ').strip().lower()
                if confirm != 'y': continue
            break

    print("\nBye!")

if __name__ == '__main__':
    main()
