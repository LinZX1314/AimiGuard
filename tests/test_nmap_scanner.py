"""NmapScanner tests — config, XML parsing, severity, scan profiles."""
import json
import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock

from services.nmap_scanner import NmapScanner


# ── Init & config ──

def test_init_defaults():
    ns = NmapScanner()
    assert ns.nmap_path is None
    assert ns.ip_ranges == []
    assert ns.scan_interval == 604800
    assert ns.enabled is False
    assert ns._config_loaded is False


def test_ensure_config_loaded_only_once():
    ns = NmapScanner()
    ns._config_loaded = True
    ns._load_config = MagicMock()
    ns._ensure_config_loaded()
    ns._load_config.assert_not_called()


def test_load_config_db_failure():
    ns = NmapScanner()
    mock_db = MagicMock()
    mock_db.query.side_effect = Exception("db down")
    with patch("services.nmap_scanner.SessionLocal", return_value=mock_db):
        ns._load_config()
    assert ns.enabled is False
    mock_db.close.assert_called_once()


# ── execute_nmap_scan ──

def test_execute_nmap_no_path():
    ns = NmapScanner()
    ns.nmap_path = None
    assert ns.execute_nmap_scan("10.0.0.1", "-sS", "/tmp/out.xml") is False


def test_execute_nmap_path_not_exists():
    ns = NmapScanner()
    ns.nmap_path = "/nonexistent/nmap"
    assert ns.execute_nmap_scan("10.0.0.1", "-sS", "/tmp/out.xml") is False


# ── parse_nmap_xml ──

def test_parse_nmap_xml_valid():
    xml_content = """<?xml version="1.0"?>
<nmaprun>
  <host>
    <status state="up"/>
    <address addr="10.0.0.1" addrtype="ipv4"/>
    <address addr="AA:BB:CC:DD:EE:FF" addrtype="mac" vendor="Cisco"/>
    <hostnames><hostname name="router.local"/></hostnames>
    <os><osmatch name="Linux 3.x" accuracy="95"/></os>
    <ports>
      <port protocol="tcp" portid="22">
        <state state="open"/>
        <service name="ssh" product="OpenSSH" version="7.9"/>
      </port>
      <port protocol="tcp" portid="80">
        <state state="open"/>
        <service name="http" product="nginx"/>
      </port>
      <port protocol="tcp" portid="443">
        <state state="closed"/>
        <service name="https"/>
      </port>
    </ports>
  </host>
  <host>
    <status state="down"/>
    <address addr="10.0.0.2" addrtype="ipv4"/>
  </host>
</nmaprun>"""
    ns = NmapScanner()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False, encoding="utf-8") as f:
        f.write(xml_content)
        f.flush()
        path = f.name

    try:
        hosts = ns.parse_nmap_xml(path)
        assert len(hosts) == 1
        h = hosts[0]
        assert h["ip"] == "10.0.0.1"
        assert h["mac_address"] == "AA:BB:CC:DD:EE:FF"
        assert h["vendor"] == "Cisco"
        assert h["hostname"] == "router.local"
        assert h["os_type"] == "Linux 3.x"
        assert 22 in h["open_ports"]
        assert 80 in h["open_ports"]
        assert 443 not in h["open_ports"]
        assert len(h["services"]) == 2
    finally:
        os.unlink(path)


def test_parse_nmap_xml_invalid_file():
    ns = NmapScanner()
    hosts = ns.parse_nmap_xml("/nonexistent/file.xml")
    assert hosts == []


def test_parse_nmap_xml_empty():
    ns = NmapScanner()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False, encoding="utf-8") as f:
        f.write("<nmaprun></nmaprun>")
        f.flush()
        path = f.name
    try:
        hosts = ns.parse_nmap_xml(path)
        assert hosts == []
    finally:
        os.unlink(path)


# ── save_scan_results ──

def test_save_scan_results():
    ns = NmapScanner()
    mock_db = MagicMock()
    hosts_data = [
        {
            "ip": "10.0.0.1",
            "mac_address": "AA:BB",
            "vendor": "Test",
            "hostname": "host1",
            "state": "up",
            "os_type": "Linux",
            "os_accuracy": "95",
            "open_ports": [22, 80],
            "services": [
                {"port": 22, "protocol": "tcp", "service": "ssh", "product": "OpenSSH", "version": "7.9"},
            ],
        }
    ]
    with patch("services.nmap_scanner.ScanFinding"):
        count = ns.save_scan_results(1, hosts_data, mock_db, "tr1")
    assert count == 1
    mock_db.commit.assert_called_once()


def test_save_scan_results_empty():
    ns = NmapScanner()
    mock_db = MagicMock()
    count = ns.save_scan_results(1, [], mock_db, "tr1")
    assert count == 0


# ── get_win7_hosts ──

def test_get_win7_hosts():
    ns = NmapScanner()
    mock_db = MagicMock()
    finding1 = MagicMock()
    finding1.os_type = "Microsoft Windows 7 Professional"
    finding1.asset = "10.0.0.5"
    finding1.mac_address = "AA:BB"
    finding1.vendor = "Dell"
    finding1.hostname = "win7-pc"
    finding1.state = "up"
    finding1.os_accuracy = "90"
    finding1.evidence = json.dumps({"open_ports": [445], "services": []})

    finding2 = MagicMock()
    finding2.os_type = "Linux 5.x"
    finding2.asset = "10.0.0.6"
    finding2.evidence = "{}"

    mock_db.query.return_value.filter.return_value.all.return_value = [finding1, finding2]
    result = ns.get_win7_hosts(1, mock_db)
    assert len(result) == 1
    assert result[0]["ip"] == "10.0.0.5"
    assert 445 in result[0]["open_ports"]


def test_get_win7_hosts_2008r2():
    ns = NmapScanner()
    mock_db = MagicMock()
    finding = MagicMock()
    finding.os_type = "Windows Server 2008 R2"
    finding.asset = "10.0.0.7"
    finding.mac_address = ""
    finding.vendor = ""
    finding.hostname = "srv"
    finding.state = "up"
    finding.os_accuracy = "85"
    finding.evidence = json.dumps({"open_ports": [3389], "services": []})

    mock_db.query.return_value.filter.return_value.all.return_value = [finding]
    result = ns.get_win7_hosts(1, mock_db)
    assert len(result) == 1


def test_get_win7_hosts_none():
    ns = NmapScanner()
    mock_db = MagicMock()
    finding = MagicMock()
    finding.os_type = "Ubuntu 22.04"
    finding.evidence = "{}"
    mock_db.query.return_value.filter.return_value.all.return_value = [finding]
    result = ns.get_win7_hosts(1, mock_db)
    assert result == []
