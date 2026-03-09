"""api/report.py tests — _extract_summary, _resolve_report_path, _get_file_size."""
import os
import tempfile
import pytest
from pathlib import Path

from api.report import _extract_summary


# ── _extract_summary ──

def test_extract_summary_heading():
    md = "# Daily Report\nSome details here."
    result = _extract_summary(md, "fallback")
    assert result == "Daily Report"


def test_extract_summary_plain():
    md = "No heading, just text."
    result = _extract_summary(md, "fallback")
    assert result == "No heading, just text."


def test_extract_summary_empty():
    result = _extract_summary("", "fallback text")
    assert result == "fallback text"


def test_extract_summary_none():
    result = _extract_summary(None, "default")
    assert result == "default"


def test_extract_summary_truncates():
    long_line = "x" * 600
    result = _extract_summary(long_line, "fb")
    assert len(result) == 500


def test_extract_summary_blank_lines():
    md = "\n\n\n  \n# Actual Title"
    result = _extract_summary(md, "fb")
    assert result == "Actual Title"


def test_extract_summary_multi_hash():
    md = "## Sub Heading"
    result = _extract_summary(md, "fb")
    assert result == "Sub Heading"
