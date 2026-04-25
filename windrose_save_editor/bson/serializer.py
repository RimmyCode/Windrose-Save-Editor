from __future__ import annotations

import struct

from .types import BSONArray, BSONDatetime, BSONDoc, BSONInt64, BSONValue


def _cstring(s: str) -> bytes:
    return s.encode("utf-8") + b"\x00"


def _serialize_value(val: BSONValue) -> tuple[int, bytes]:
    """Return (bson_type_byte, payload) for a Python value."""
    # bool must come before int — bool is a subclass of int in Python
    if isinstance(val, bool):
        return 0x08, bytes([1 if val else 0])
    if isinstance(val, BSONDatetime):
        return 0x09, struct.pack("<q", int(val))
    if isinstance(val, BSONInt64):
        return 0x12, struct.pack("<q", int(val))
    if isinstance(val, int):
        if -(2**31) <= val <= 2**31 - 1:
            return 0x10, struct.pack("<i", val)
        return 0x12, struct.pack("<q", val)
    if isinstance(val, float):
        return 0x01, struct.pack("<d", val)
    if isinstance(val, str):
        encoded = val.encode("utf-8") + b"\x00"
        return 0x02, struct.pack("<I", len(encoded)) + encoded
    if val is None:
        return 0x0A, b""
    if isinstance(val, dict):
        if "$binary" in val:
            raw = bytes.fromhex(val["$binary"])
            return 0x05, struct.pack("<I", len(raw)) + bytes([val.get("$subtype", 0)]) + raw
        if isinstance(val, BSONArray):
            return 0x04, serialize_bson_doc(val)
        return 0x03, serialize_bson_doc(val)
    raise TypeError(f"Cannot serialize {type(val)}: {val!r}")


def serialize_bson_doc(doc: BSONDoc) -> bytes:
    body = b""
    for key, val in doc.items():
        vtype, payload = _serialize_value(val)
        body += bytes([vtype]) + _cstring(key) + payload
    body += b"\x00"
    size = 4 + len(body)
    return struct.pack("<I", size) + body
