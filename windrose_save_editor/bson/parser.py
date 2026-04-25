from __future__ import annotations

import struct

from .types import BSONArray, BSONDatetime, BSONDoc, BSONInt64, BSONValue


def _read_cstring(data: bytes, pos: int) -> tuple[str, int]:
    end = data.index(0, pos)
    return data[pos:end].decode("utf-8", errors="replace"), end + 1


def parse_bson(data: bytes, pos: int = 0) -> BSONDoc:
    doc_size = struct.unpack_from("<I", data, pos)[0]
    end = pos + doc_size
    pos += 4
    doc: BSONDoc = {}

    while pos < end - 1:
        btype = data[pos]
        pos += 1
        if btype == 0:
            break

        name, pos = _read_cstring(data, pos)

        match btype:
            case 0x01:  # double
                doc[name] = struct.unpack_from("<d", data, pos)[0]
                pos += 8
            case 0x02:  # UTF-8 string
                slen = struct.unpack_from("<I", data, pos)[0]
                pos += 4
                doc[name] = data[pos : pos + slen - 1].decode("utf-8", errors="replace")
                pos += slen
            case 0x03:  # embedded document
                subdoc_size = struct.unpack_from("<I", data, pos)[0]
                doc[name] = parse_bson(data, pos)
                pos += subdoc_size
            case 0x04:  # array — preserve subtype for round-trip
                subdoc_size = struct.unpack_from("<I", data, pos)[0]
                doc[name] = BSONArray(parse_bson(data, pos))
                pos += subdoc_size
            case 0x05:  # binary
                blen = struct.unpack_from("<I", data, pos)[0]
                pos += 4
                subtype = data[pos]
                pos += 1
                doc[name] = {"$binary": data[pos : pos + blen].hex(), "$subtype": subtype}
                pos += blen
            case 0x08:  # boolean
                doc[name] = bool(data[pos])
                pos += 1
            case 0x09:  # UTC datetime — preserve subtype for round-trip
                doc[name] = BSONDatetime(struct.unpack_from("<q", data, pos)[0])
                pos += 8
            case 0x0A:  # null
                doc[name] = None
            case 0x10:  # int32
                doc[name] = struct.unpack_from("<i", data, pos)[0]
                pos += 4
            case 0x12:  # int64 — preserve subtype for round-trip
                doc[name] = BSONInt64(struct.unpack_from("<q", data, pos)[0])
                pos += 8
            case _:
                raise ValueError(f"Unknown BSON type 0x{btype:02x} at pos {pos - 1}, field '{name}'")

    return doc
