"""Crypto service tests — AES-GCM encrypt/decrypt/re-encrypt + key versioning."""
import base64
import os
import pytest


def _reset_crypto():
    """Reset the crypto service's key registry for test isolation."""
    from services import crypto_service
    crypto_service._KEY_REGISTRY.clear()
    crypto_service._CURRENT_VERSION = "v1"


# ── Basic encrypt / decrypt ──

def test_encrypt_returns_tuple():
    _reset_crypto()
    from services import crypto_service
    result = crypto_service.encrypt("hello world")
    assert isinstance(result, tuple)
    assert len(result) == 2
    ciphertext_b64, key_version = result
    assert isinstance(ciphertext_b64, str)
    assert key_version == "v1"


def test_decrypt_roundtrip():
    _reset_crypto()
    from services import crypto_service
    plaintext = "sensitive password 123!@#"
    ct, ver = crypto_service.encrypt(plaintext)
    decrypted = crypto_service.decrypt(ct, ver)
    assert decrypted == plaintext


def test_encrypt_produces_unique_ciphertexts():
    _reset_crypto()
    from services import crypto_service
    ct1, _ = crypto_service.encrypt("same text")
    ct2, _ = crypto_service.encrypt("same text")
    assert ct1 != ct2  # different nonces → different ciphertexts


def test_decrypt_wrong_version_raises():
    _reset_crypto()
    from services import crypto_service
    ct, _ = crypto_service.encrypt("test")
    with pytest.raises(ValueError, match="未知密钥版本"):
        crypto_service.decrypt(ct, "v99")


def test_decrypt_tampered_ciphertext_raises():
    _reset_crypto()
    from services import crypto_service
    ct, ver = crypto_service.encrypt("test")
    blob = bytearray(base64.urlsafe_b64decode(ct))
    blob[-1] ^= 0xFF  # tamper with auth tag
    tampered = base64.urlsafe_b64encode(bytes(blob)).decode("ascii")
    with pytest.raises(Exception):  # InvalidTag from cryptography
        crypto_service.decrypt(tampered, ver)


# ── Key versioning ──

def test_key_version_default():
    _reset_crypto()
    from services import crypto_service
    ver = crypto_service.get_current_key_version()
    assert ver == "v1"


def test_env_key_v1(monkeypatch):
    _reset_crypto()
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from services import crypto_service
    key = AESGCM.generate_key(bit_length=256)
    key_b64 = base64.urlsafe_b64encode(key).decode("ascii")
    monkeypatch.setenv("CREDENTIAL_KEY_V1", key_b64)
    ct, ver = crypto_service.encrypt("env key test")
    assert ver == "v1"
    assert crypto_service.decrypt(ct, ver) == "env key test"


def test_env_key_v2_becomes_current(monkeypatch):
    _reset_crypto()
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from services import crypto_service
    k1 = base64.urlsafe_b64encode(AESGCM.generate_key(bit_length=256)).decode()
    k2 = base64.urlsafe_b64encode(AESGCM.generate_key(bit_length=256)).decode()
    monkeypatch.setenv("CREDENTIAL_KEY_V1", k1)
    monkeypatch.setenv("CREDENTIAL_KEY_V2", k2)
    ver = crypto_service.get_current_key_version()
    assert ver == "v2"
    ct, v = crypto_service.encrypt("v2 test")
    assert v == "v2"
    assert crypto_service.decrypt(ct, v) == "v2 test"


# ── Re-encryption (key rotation) ──

def test_re_encrypt():
    _reset_crypto()
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from services import crypto_service
    # Encrypt with v1
    ct_v1, ver_v1 = crypto_service.encrypt("rotate me")
    assert ver_v1 == "v1"

    # Simulate adding v2 key
    crypto_service._KEY_REGISTRY["v2"] = AESGCM.generate_key(bit_length=256)
    crypto_service._CURRENT_VERSION = "v2"

    # Re-encrypt from v1 → v2
    ct_v2, ver_v2 = crypto_service.re_encrypt(ct_v1, "v1")
    assert ver_v2 == "v2"
    assert ct_v2 != ct_v1

    # Decrypt with v2
    assert crypto_service.decrypt(ct_v2, "v2") == "rotate me"


# ── Edge cases ──

def test_encrypt_empty_string():
    _reset_crypto()
    from services import crypto_service
    ct, ver = crypto_service.encrypt("")
    assert crypto_service.decrypt(ct, ver) == ""


def test_encrypt_unicode():
    _reset_crypto()
    from services import crypto_service
    text = "密码测试 🔐 パスワード"
    ct, ver = crypto_service.encrypt(text)
    assert crypto_service.decrypt(ct, ver) == text


def test_ciphertext_is_valid_base64():
    _reset_crypto()
    from services import crypto_service
    ct, _ = crypto_service.encrypt("base64 check")
    blob = base64.urlsafe_b64decode(ct)
    assert len(blob) > 12  # at least nonce(12) + some ciphertext
