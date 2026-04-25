"""
BSON tests focused on what matters:
  - Round-trip fidelity (the contract the save editor depends on)
  - Type subclass preservation (BSONArray/BSONDatetime/BSONInt64 must survive parse→serialize→parse)
  - Edge cases that could silently corrupt a save
"""
import struct
import pytest

from windrose_save_editor.bson.types import BSONArray, BSONDatetime, BSONInt64
from windrose_save_editor.bson.parser import parse_bson
from windrose_save_editor.bson.serializer import serialize_bson_doc


def roundtrip(doc: dict) -> dict:
    return parse_bson(serialize_bson_doc(doc))


# ── Round-trip: all supported BSON types in one document ─────────────────────

def test_roundtrip_all_types():
    doc = {
        "a_int32":    42,
        "a_int64":    BSONInt64(2**40),
        "a_double":   3.14,
        "a_string":   "hello windrose",
        "a_bool_t":   True,
        "a_bool_f":   False,
        "a_null":     None,
        "a_datetime": BSONDatetime(1_700_000_000_000),
        "a_array":    BSONArray({"0": "first", "1": "second"}),
        "a_subdoc":   {"nested": 99},
        "a_binary":   {"$binary": "deadbeef", "$subtype": 0},
    }
    assert roundtrip(doc) == doc


def test_roundtrip_is_byte_perfect():
    """Serialize → parse → serialize must produce identical bytes (critical for save integrity)."""
    doc = {
        "PlayerName": "Thorben",
        "Level":      BSONInt64(42),
        "Timestamp":  BSONDatetime(1_700_000_000_000),
        "Flags":      BSONArray({"0": True, "1": False}),
    }
    first_bytes = serialize_bson_doc(doc)
    second_bytes = serialize_bson_doc(parse_bson(first_bytes))
    assert first_bytes == second_bytes


# ── Type subclass preservation ────────────────────────────────────────────────

def test_bsonarray_preserved_through_roundtrip():
    doc = {"items": BSONArray({"0": "sword", "1": "shield"})}
    result = roundtrip(doc)
    assert isinstance(result["items"], BSONArray)


def test_bsondatetime_preserved_through_roundtrip():
    doc = {"ts": BSONDatetime(1_700_000_000_000)}
    result = roundtrip(doc)
    assert isinstance(result["ts"], BSONDatetime)
    assert result["ts"] == 1_700_000_000_000


def test_bsonint64_preserved_through_roundtrip():
    doc = {"big": BSONInt64(2**40)}
    result = roundtrip(doc)
    assert isinstance(result["big"], BSONInt64)
    assert result["big"] == 2**40


# ── int32 vs int64 boundary ───────────────────────────────────────────────────

def test_int32_max_stays_int32():
    """Values within int32 range must not become BSONInt64 after round-trip."""
    doc = {"v": 2**31 - 1}
    result = roundtrip(doc)
    assert result["v"] == 2**31 - 1
    assert not isinstance(result["v"], BSONInt64)


def test_value_above_int32_becomes_int64():
    doc = {"v": 2**31}
    result = roundtrip(doc)
    assert result["v"] == 2**31


# ── bool must not be confused with int ───────────────────────────────────────

def test_bool_survives_roundtrip():
    """bool is a subclass of int; serializer must write 0x08, not 0x10."""
    doc = {"flag": True}
    raw = serialize_bson_doc(doc)
    # type byte for the first field must be 0x08 (bool), not 0x10 (int32)
    # layout: 4-byte size | 0x08 | "flag\x00" | 0x01
    type_byte_offset = 4
    assert raw[type_byte_offset] == 0x08
    assert roundtrip(doc)["flag"] is True


# ── Nested and empty documents ────────────────────────────────────────────────

def test_empty_doc_roundtrip():
    assert roundtrip({}) == {}


def test_deeply_nested_doc():
    doc = {"a": {"b": {"c": {"d": 1}}}}
    assert roundtrip(doc) == doc


# ── Unknown BSON type raises clearly ─────────────────────────────────────────

def test_unknown_bson_type_raises():
    # Craft a minimal BSON doc with an unknown type byte (0xFF)
    name = b"x\x00"
    body = bytes([0xFF]) + name + b"\x00"  # type=0xFF, key="x", terminator
    raw = struct.pack("<I", 4 + len(body)) + body
    with pytest.raises(ValueError, match="Unknown BSON type"):
        parse_bson(raw)
