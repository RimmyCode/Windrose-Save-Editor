from windrose_save_editor.crc import crc32c, wal_masked_crc


def test_crc32c_empty():
    assert crc32c(b"") == 0x00000000


def test_crc32c_known_vector():
    # RFC 3720 test vector: crc32c("123456789") == 0xE3069283
    assert crc32c(b"123456789") == 0xE3069283


def test_crc32c_single_byte():
    assert crc32c(b"\x00") == 0x527D5351


def test_wal_masked_crc_is_deterministic():
    a = wal_masked_crc(b"hello world")
    b = wal_masked_crc(b"hello world")
    assert a == b


def test_wal_masked_crc_differs_from_raw():
    data = b"some rocksdb record"
    raw = crc32c(data)
    masked = wal_masked_crc(data)
    assert raw != masked


def test_wal_masked_crc_fits_uint32():
    result = wal_masked_crc(b"x" * 1000)
    assert 0 <= result <= 0xFFFFFFFF
