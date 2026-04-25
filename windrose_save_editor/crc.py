import struct

_POLY = 0x82F63B78  # Castagnoli polynomial (reflected)

_TABLE = []
for _i in range(256):
    _c = _i
    for _ in range(8):
        _c = (_c >> 1) ^ _POLY if _c & 1 else _c >> 1
    _TABLE.append(_c)


def crc32c(data: bytes) -> int:
    """CRC32C (Castagnoli). Pure Python — binascii uses CRC32-IEEE which produces wrong RocksDB checksums."""
    crc = 0xFFFFFFFF
    for byte in data:
        crc = (crc >> 8) ^ _TABLE[(crc ^ byte) & 0xFF]
    return crc ^ 0xFFFFFFFF


def wal_masked_crc(data: bytes) -> int:
    """RocksDB masked CRC: rotate-right 15 then add magic constant."""
    raw = crc32c(data)
    return (((raw >> 15) | (raw << 17)) + 0xA282EAD8) & 0xFFFFFFFF
