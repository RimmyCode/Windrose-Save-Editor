from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

from windrose_save_editor.crc import wal_masked_crc
from windrose_save_editor.rocksdb.wal import read_varint, write_varint


@dataclass
class ManifestInfo:
    last_sequence: int
    next_file_number: int
    log_number: int


def parse_manifest(save_dir: Path) -> ManifestInfo:
    """
    Parse the RocksDB MANIFEST file to extract version-edit metadata.

    Reads the last (most recent) MANIFEST-* file in save_dir and returns
    the highest last_sequence, next_file_number, and log_number found.
    These values are required when writing a valid WAL the game will replay.

    Returns a ManifestInfo with all zeros if no MANIFEST file is found.
    """
    manifests = sorted(save_dir.glob("MANIFEST-*"))
    if not manifests:
        return ManifestInfo(last_sequence=0, next_file_number=0, log_number=0)

    raw = manifests[-1].read_bytes()

    last_sequence: int = 0
    next_file_number: int = 0
    log_number: int = 0

    pos = 0
    while pos < len(raw):
        if pos + 7 > len(raw):
            break
        length = struct.unpack_from("<H", raw, pos + 4)[0]
        chunk = raw[pos + 7 : pos + 7 + length]
        pos += 7 + length
        rem = pos % 32768
        if 0 < rem < 7:
            pos += 32768 - rem

        p = 0
        while p < len(chunk):
            try:
                tag, np = read_varint(chunk, p)
                match tag:
                    case 2:
                        v, np = read_varint(chunk, np)
                        log_number = max(log_number, v)
                    case 3:
                        v, np = read_varint(chunk, np)
                        next_file_number = max(next_file_number, v)
                    case 4:
                        v, np = read_varint(chunk, np)
                        last_sequence = max(last_sequence, v)
                p += 1
            except Exception:
                p += 1

    return ManifestInfo(
        last_sequence=last_sequence,
        next_file_number=next_file_number,
        log_number=log_number,
    )


def append_manifest_record(
    save_dir: Path,
    new_log_number: int,
    new_last_sequence: int,
    new_next_file: int,
) -> None:
    """
    Append a VersionEdit record to the MANIFEST so RocksDB replays the new WAL.

    Does nothing if no MANIFEST file exists in save_dir.
    """
    manifests = sorted(save_dir.glob("MANIFEST-*"))
    if not manifests:
        return

    body = (
        write_varint(2) + write_varint(new_log_number)
        + write_varint(3) + write_varint(new_next_file)
        + write_varint(4) + write_varint(new_last_sequence)
    )
    crc_data = bytes([1]) + body   # type=1 FULL record
    crc = wal_masked_crc(crc_data)
    record = struct.pack("<IHB", crc, len(body), 1) + body

    with open(manifests[-1], "ab") as f:
        f.write(record)
