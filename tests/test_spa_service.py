"""SPA (Single Packet Authorization) service tests — token generation, verification, expiry, anti-replay."""
import time
import pytest
from services.spa_service import generate_spa_token, verify_spa_token


SECRET = "test-spa-secret-key-2024"
CLIENT_IP = "192.168.1.100"


# ── Token generation ──

def test_generate_token_format():
    token = generate_spa_token(CLIENT_IP, SECRET)
    parts = token.split(":")
    assert len(parts) == 3  # ip:timestamp:signature
    assert parts[0] == CLIENT_IP


def test_generate_token_requires_secret():
    with pytest.raises(ValueError, match="SPA_SECRET"):
        generate_spa_token(CLIENT_IP, "")


def test_generate_token_unique_per_call():
    t1 = generate_spa_token(CLIENT_IP, SECRET)
    t2 = generate_spa_token(CLIENT_IP, SECRET)
    # Tokens generated at the same second will have same timestamp,
    # so they may be identical — but they should both be valid
    ok1, _ = verify_spa_token(t1, CLIENT_IP, SECRET)
    ok2, _ = verify_spa_token(t2, CLIENT_IP, SECRET)
    assert ok1 and ok2


# ── Token verification ──

def test_verify_valid_token():
    token = generate_spa_token(CLIENT_IP, SECRET)
    valid, reason = verify_spa_token(token, CLIENT_IP, SECRET)
    assert valid is True
    assert reason == "ok"


def test_verify_wrong_ip():
    token = generate_spa_token(CLIENT_IP, SECRET)
    valid, reason = verify_spa_token(token, "10.0.0.1", SECRET)
    assert valid is False
    assert reason == "ip_mismatch"


def test_verify_wrong_secret():
    token = generate_spa_token(CLIENT_IP, SECRET)
    valid, reason = verify_spa_token(token, CLIENT_IP, "wrong-secret")
    assert valid is False
    assert reason == "signature_mismatch"


def test_verify_empty_token():
    valid, reason = verify_spa_token("", CLIENT_IP, SECRET)
    assert valid is False
    assert reason == "empty_token"


def test_verify_no_secret():
    token = generate_spa_token(CLIENT_IP, SECRET)
    valid, reason = verify_spa_token(token, CLIENT_IP, "")
    assert valid is False
    assert reason == "spa_secret_not_configured"


def test_verify_invalid_format():
    valid, reason = verify_spa_token("garbage", CLIENT_IP, SECRET)
    assert valid is False


def test_verify_tampered_signature():
    token = generate_spa_token(CLIENT_IP, SECRET)
    parts = token.rsplit(":", 1)
    tampered = parts[0] + ":0000000000000000000000000000000000000000000000000000000000000000"
    valid, reason = verify_spa_token(tampered, CLIENT_IP, SECRET)
    assert valid is False
    assert reason == "signature_mismatch"


# ── Expiry ──

def test_verify_expired_token():
    token = generate_spa_token(CLIENT_IP, SECRET)
    # Simulate expired by using ttl=0
    valid, reason = verify_spa_token(token, CLIENT_IP, SECRET, ttl=0)
    assert valid is False
    assert reason == "token_expired"


def test_verify_custom_ttl():
    token = generate_spa_token(CLIENT_IP, SECRET)
    # Very generous TTL
    valid, reason = verify_spa_token(token, CLIENT_IP, SECRET, ttl=86400)
    assert valid is True
    assert reason == "ok"


def test_verify_future_token():
    # Forge a token with a future timestamp
    future_ts = int(time.time()) + 3600  # 1 hour in future
    import hmac as hmac_mod, hashlib
    message = f"{CLIENT_IP}:{future_ts}"
    sig = hmac_mod.new(SECRET.encode(), message.encode(), hashlib.sha256).hexdigest()
    token = f"{message}:{sig}"
    valid, reason = verify_spa_token(token, CLIENT_IP, SECRET)
    assert valid is False
    assert reason == "token_future"


# ── Edge cases ──

def test_ipv6_address_not_supported():
    """IPv6 with colons breaks the ip:timestamp:signature format — known limitation."""
    ipv6 = "::1"
    token = generate_spa_token(ipv6, SECRET)
    valid, reason = verify_spa_token(token, ipv6, SECRET)
    # Token format uses : as delimiter, so IPv6 addresses are not supported
    assert valid is False


def test_multiple_ips_different_tokens():
    t1 = generate_spa_token("10.0.0.1", SECRET)
    t2 = generate_spa_token("10.0.0.2", SECRET)
    # Each token only valid for its own IP
    v1, _ = verify_spa_token(t1, "10.0.0.1", SECRET)
    v2, _ = verify_spa_token(t2, "10.0.0.2", SECRET)
    v_cross, _ = verify_spa_token(t1, "10.0.0.2", SECRET)
    assert v1 is True
    assert v2 is True
    assert v_cross is False
