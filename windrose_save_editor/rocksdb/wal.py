from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

from windrose_save_editor.crc import wal_masked_crc

BLOCK_SIZE = 32768


@dataclass
class WalEntry:
    sequence: int
    cf_id: int
    player_key: bytes
    bson_bytes: bytes
    batch_count: int


def read_varint(data: bytes, pos: int) -> tuple[int, int]:
    result, shift = 0, 0
    while True:
        b = data[pos]; pos += 1
        result |= (b & 0x7F) << shift
        if not (b & 0x80):
            break
        shift += 7
    return result, pos


def write_varint(n: int) -> bytes:
    out = []
    while True:
        b = n & 0x7F; n >>= 7
        if n:
            b |= 0x80
        out.append(b)
        if not n:
            break
    return bytes(out)


def read_wal(log_path: Path) -> WalEntry | None:
    """
    Parse a RocksDB WAL log file and return the last player entry.

    Reassembles fragmented WAL blocks, then scans all write batches to find
    the most recent entry in CF 2 (R5BLPlayer) with a 32-byte key.

    Returns a WalEntry, or None if the WAL is empty or contains no player data.
    """
    with open(log_path, "rb") as f:
        raw = f.read()

    # Reassemble payload from block fragments
    payload = b""
    pos = 0
    while pos < len(raw):
        if pos + 7 > len(raw):
            break
        # crc(4) + length(2) + type(1)
        length = struct.unpack_from("<H", raw, pos + 4)[0]
        rtype = raw[pos + 6]
        chunk = raw[pos + 7 : pos + 7 + length]
        if rtype in (1, 4):    # FULL or LAST
            payload += chunk
        elif rtype in (2, 3):  # FIRST or MIDDLE
            payload += chunk
        pos += BLOCK_SIZE

    # WriteBatch header is 12 bytes (seq:8 + count:4)
    if len(payload) < 12:
        return None  # empty WAL -- data is in SST files

    # Scan ALL write batches to find the LAST player entry (CF 2, 32-byte key).
    # The game appends multiple batches per session; we want the most recent.
    last_seq: int | None = None
    last_cf_id: int = 2
    last_player_key: bytes | None = None
    last_bson: bytes | None = None
    last_batch_count: int = 1

    pos = 0
    while pos + 12 <= len(payload):
        try:
            batch_seq = struct.unpack_from("<Q", payload, pos)[0]
            batch_count = struct.unpack_from("<I", payload, pos + 8)[0]
            p = pos + 12
            for _ in range(batch_count):
                if p >= len(payload):
                    break
                etype = payload[p]; p += 1
                match etype:
                    case 0x01 | 0x05:  # default-CF or named-CF value
                        cf_id_entry = 0
                        if etype == 0x05:
                            cf_id_entry, p = read_varint(payload, p)
                        key_len, p = read_varint(payload, p)
                        key = payload[p : p + key_len]; p += key_len
                        val_len, p = read_varint(payload, p)
                        val = payload[p : p + val_len]; p += val_len
                        # Player key = CF 2, 32 bytes, large BSON value
                        if (
                            cf_id_entry == 2
                            and key_len == 32
                            and val_len > 1000
                            and len(val) >= 4
                            and struct.unpack_from("<I", val, 0)[0] == val_len
                        ):
                            last_player_key = key
                            last_bson = val
                            last_seq = batch_seq
                            last_batch_count = batch_count
                    case 0x00 | 0x04:  # deletion -- skip key only
                        if etype == 0x04:
                            _, p = read_varint(payload, p)
                        key_len, p = read_varint(payload, p)
                        p += key_len
                    case _:
                        break  # unknown entry type -- stop scanning this batch
            pos = p
        except Exception:
            break  # corrupt / end of WAL

    if last_bson is None or last_seq is None or last_player_key is None:
        return None

    return WalEntry(
        sequence=last_seq,
        cf_id=last_cf_id,
        player_key=last_player_key,
        bson_bytes=last_bson,
        batch_count=last_batch_count,
    )


def write_wal(
    log_path: Path,
    seq: int,
    cf_id: int,
    player_key: bytes,
    bson_bytes: bytes,
) -> None:
    """
    Write a new WAL log file with the modified BSON payload.

    Handles RocksDB block fragmentation and CRC32C checksums.
    """
    # Build WriteBatch payload
    batch = (
        struct.pack("<Q", seq)
        + struct.pack("<I", 1)        # count = 1 entry
        + bytes([0x05])               # kTypeColumnFamilyValue
        + write_varint(cf_id)
        + write_varint(len(player_key))
        + player_key
        + write_varint(len(bson_bytes))
        + bson_bytes
    )

    # Fragment into 32KB blocks with 7-byte record headers
    MAX_DATA = BLOCK_SIZE - 7
    fragments: list[bytes] = []
    offset = 0
    total = len(batch)

    while offset < total:
        chunk = batch[offset : offset + MAX_DATA]
        offset += len(chunk)
        is_first = offset - len(chunk) == 0
        is_last = offset >= total

        match (is_first, is_last):
            case (True, True):
                rtype = 1  # FULL
            case (True, False):
                rtype = 2  # FIRST
            case (False, False):
                rtype = 3  # MIDDLE
            case _:
                rtype = 4  # LAST

        crc_data = bytes([rtype]) + chunk
        crc = wal_masked_crc(crc_data)
        header = struct.pack("<I", crc) + struct.pack("<H", len(chunk)) + bytes([rtype])
        fragments.append(header + chunk)

    # Pad each fragment to block boundary
    output = b""
    for frag in fragments:
        output += frag
        pad = BLOCK_SIZE - (len(output) % BLOCK_SIZE)
        if pad < BLOCK_SIZE:
            output += bytes([0]) * pad

    with open(log_path, "wb") as f:
        f.write(output)
