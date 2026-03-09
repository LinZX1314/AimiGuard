"""api/scan.py tests — _actor_name, _normalize_target_type/target/tags, profiles."""
import pytest
from unittest.mock import MagicMock
from fastapi import HTTPException

from api.scan import (
    _actor_name,
    _normalize_target_type,
    _normalize_target,
    _normalize_tags,
    SCAN_PROFILES,
    NUCLEI_PROFILES,
    ASSET_TARGET_TYPES,
    DOMAIN_PATTERN,
)


# ── _actor_name ──

def test_actor_name_from_object():
    user = MagicMock()
    user.username = "admin"
    assert _actor_name(user) == "admin"


def test_actor_name_from_dict():
    assert _actor_name({"username": "op"}) == "op"


def test_actor_name_missing():
    assert _actor_name({}) == "unknown"
    assert _actor_name(object()) == "unknown"


# ── _normalize_target_type ──

def test_normalize_target_type_valid():
    assert _normalize_target_type("ip") == "IP"
    assert _normalize_target_type("CIDR") == "CIDR"
    assert _normalize_target_type(" domain ") == "DOMAIN"


def test_normalize_target_type_invalid():
    with pytest.raises(HTTPException) as exc_info:
        _normalize_target_type("invalid")
    assert exc_info.value.status_code == 400


# ── _normalize_target ──

def test_normalize_target_ip():
    assert _normalize_target("10.0.0.1", "IP") == "10.0.0.1"


def test_normalize_target_ip_invalid():
    with pytest.raises(HTTPException):
        _normalize_target("999.999.999.999", "IP")


def test_normalize_target_cidr():
    assert _normalize_target("10.0.0.0/24", "CIDR") == "10.0.0.0/24"


def test_normalize_target_cidr_no_mask():
    with pytest.raises(HTTPException):
        _normalize_target("10.0.0.0", "CIDR")


def test_normalize_target_domain():
    assert _normalize_target("example.com", "DOMAIN") == "example.com"


def test_normalize_target_domain_invalid():
    with pytest.raises(HTTPException):
        _normalize_target("not valid domain!", "DOMAIN")


def test_normalize_target_empty():
    with pytest.raises(HTTPException):
        _normalize_target("", "IP")


# ── _normalize_tags ──

def test_normalize_tags_default():
    assert _normalize_tags(None, "IP") == "ip"
    assert _normalize_tags("", "CIDR") == "cidr"


def test_normalize_tags_custom():
    assert _normalize_tags("web,db", "IP") == "web,db"


def test_normalize_tags_dedup():
    result = _normalize_tags("web,Web,WEB", "IP")
    assert result == "web"


def test_normalize_tags_chinese_comma():
    result = _normalize_tags("web，db", "IP")
    assert result == "web,db"


def test_normalize_tags_blank_items():
    result = _normalize_tags(",web,,db,", "IP")
    assert result == "web,db"


# ── Profiles ──

def test_scan_profiles_keys():
    assert "quick" in SCAN_PROFILES
    assert "default" in SCAN_PROFILES
    assert "comprehensive" in SCAN_PROFILES
    assert "vuln" in SCAN_PROFILES


def test_nuclei_profiles_keys():
    assert "cve" in NUCLEI_PROFILES
    assert "full" in NUCLEI_PROFILES


def test_asset_target_types():
    assert ASSET_TARGET_TYPES == {"IP", "CIDR", "DOMAIN"}


# ── DOMAIN_PATTERN ──

def test_domain_pattern_valid():
    assert DOMAIN_PATTERN.fullmatch("example.com")
    assert DOMAIN_PATTERN.fullmatch("sub.example.com")


def test_domain_pattern_invalid():
    assert DOMAIN_PATTERN.fullmatch("-invalid.com") is None
    assert DOMAIN_PATTERN.fullmatch("") is None
