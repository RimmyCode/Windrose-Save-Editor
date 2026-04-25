from __future__ import annotations

from typing import Union

# Recursive type alias for any value that can appear in a BSON document.
# Forward references needed because BSONDoc references BSONValue and vice versa.
BSONValue = Union[
    bool,
    int,
    float,
    str,
    None,
    "BSONDatetime",
    "BSONInt64",
    "BSONArray",
    "BSONDoc",
    dict,  # binary blobs: {"$binary": hex_str, "$subtype": int}
]

BSONDoc = dict[str, BSONValue]


class BSONArray(dict):
    """dict subclass that round-trips as BSON type 0x04 (Array)."""


class BSONDatetime(int):
    """int subclass that round-trips as BSON type 0x09 (UTC datetime, milliseconds)."""


class BSONInt64(int):
    """int subclass that round-trips as BSON type 0x12 (int64)."""
