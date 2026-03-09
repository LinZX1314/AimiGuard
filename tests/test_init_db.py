"""init_db.py tests — hash_password helper."""
from init_db import hash_password


def test_hash_password_sha256():
    h = hash_password("admin123")
    assert len(h) == 64  # SHA-256 hex digest
    assert h == hash_password("admin123")  # deterministic


def test_hash_password_different_inputs():
    assert hash_password("a") != hash_password("b")


def test_hash_password_empty():
    h = hash_password("")
    assert len(h) == 64
