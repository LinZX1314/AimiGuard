"""Scanner tests — NmapParser, severity classification, Scanner lifecycle, Nuclei."""
import pytest
from unittest.mock import patch, MagicMock

from services.scanner import NmapParser, Scanner, _broadcast_scan_task_state


# ── NmapParser.parse_xml ──

SAMPLE_XML = """<?xml version="1.0"?>
<nmaprun>
  <host>
    <status state="up"/>
    <address addr="10.0.0.1" addrtype="ipv4"/>
    <ports>
      <port protocol="tcp" portid="22">
        <state state="open"/>
        <service name="ssh" product="OpenSSH" version="8.2"/>
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


def test_parse_xml_basic():
    findings = NmapParser.parse_xml(SAMPLE_XML)
    assert len(findings) == 2  # port 443 is closed, host 10.0.0.2 is down
    assert findings[0]["ip"] == "10.0.0.1"
    assert findings[0]["port"] == 22
    assert findings[0]["service"] == "ssh"
    assert findings[1]["port"] == 80


def test_parse_xml_with_scripts():
    xml = """<?xml version="1.0"?>
<nmaprun>
  <host>
    <status state="up"/>
    <address addr="10.0.0.1" addrtype="ipv4"/>
    <ports>
      <port protocol="tcp" portid="445">
        <state state="open"/>
        <service name="smb"/>
        <script id="smb-vuln-ms17-010" output="VULNERABLE: CVE-2017-0143"/>
      </port>
    </ports>
  </host>
</nmaprun>"""
    findings = NmapParser.parse_xml(xml)
    assert len(findings) == 1
    assert len(findings[0]["scripts"]) == 1
    assert "VULNERABLE" in findings[0]["scripts"][0]["output"]


def test_parse_xml_invalid():
    findings = NmapParser.parse_xml("not xml at all")
    assert findings == []


def test_parse_xml_empty():
    findings = NmapParser.parse_xml("<nmaprun></nmaprun>")
    assert findings == []


# ── NmapParser.determine_severity ──

def test_severity_high_risk_port():
    assert NmapParser.determine_severity("ftp", 21, []) == "HIGH"
    assert NmapParser.determine_severity("telnet", 23, []) == "HIGH"
    assert NmapParser.determine_severity("rdp", 3389, []) == "HIGH"


def test_severity_medium_risk_port():
    assert NmapParser.determine_severity("ssh", 22, []) == "MEDIUM"
    assert NmapParser.determine_severity("mysql", 3306, []) == "MEDIUM"


def test_severity_vuln_keyword():
    scripts = [{"output": "VULNERABLE to CVE-2021-44228"}]
    assert NmapParser.determine_severity("http", 80, scripts) == "HIGH"


def test_severity_system_port():
    assert NmapParser.determine_severity("unknown", 443, []) == "LOW"


def test_severity_high_port():
    assert NmapParser.determine_severity("custom", 8080, []) == "INFO"


# ── Scanner lifecycle ──

def test_scanner_init():
    with patch.dict("os.environ", {"SCANNER_MAX_CONCURRENT": "5"}):
        s = Scanner()
    assert s.max_concurrent == 5


def test_scanner_get_task_status_unknown():
    s = Scanner()
    assert s.get_task_status(999) is None


def test_scanner_get_task_status_running():
    s = Scanner()
    mock_task = MagicMock()
    mock_task.done.return_value = False
    s.running_tasks[1] = mock_task
    assert s.get_task_status(1) == "running"


def test_scanner_get_task_status_completed():
    s = Scanner()
    mock_task = MagicMock()
    mock_task.done.return_value = True
    s.running_tasks[2] = mock_task
    assert s.get_task_status(2) == "completed"


@pytest.mark.asyncio
async def test_scanner_execute_unsupported_tool():
    s = Scanner()
    with pytest.raises(ValueError, match="Unsupported scan tool"):
        await s.execute_scan(1, "10.0.0.1", tool_name="zap")


@pytest.mark.asyncio
async def test_scanner_schedule_too_many():
    s = Scanner()
    s.max_concurrent = 0
    with pytest.raises(RuntimeError, match="Too many"):
        await s.schedule_scan(1, "10.0.0.1")


@pytest.mark.asyncio
async def test_scanner_cancel_nonexistent():
    s = Scanner()
    result = await s.cancel_scan(999)
    assert result is False


# ── Nuclei helpers ──

def test_parse_nuclei_to_findings():
    s = Scanner()
    nuclei_result = {
        "findings": [
            {
                "template_id": "CVE-2021-44228",
                "host": "10.0.0.1",
                "type": "http",
                "severity": "CRITICAL",
                "description": "Log4j RCE vulnerability",
            },
            {
                "template_id": "default-login",
                "host": "10.0.0.2",
                "type": "network",
                "severity": "HIGH",
                "description": "Default credentials found",
            },
        ]
    }
    rows = s.parse_nuclei_to_findings(nuclei_result, task_id=42, trace_id="tr1")
    assert len(rows) == 2
    assert rows[0]["scan_task_id"] == 42
    assert rows[0]["vuln_id"] == "CVE-2021-44228"
    assert rows[0]["severity"] == "CRITICAL"
    assert rows[1]["service"] == "network"


def test_parse_nuclei_empty():
    s = Scanner()
    rows = s.parse_nuclei_to_findings({"findings": []}, task_id=1, trace_id="t")
    assert rows == []


# ── NUCLEI_TEMPLATE_TAGS ──

def test_nuclei_template_tags():
    assert "cve" in Scanner.NUCLEI_TEMPLATE_TAGS
    assert "network" in Scanner.NUCLEI_TEMPLATE_TAGS
