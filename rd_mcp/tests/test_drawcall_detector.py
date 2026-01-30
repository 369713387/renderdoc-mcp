# rd_mcp/tests/test_drawcall_detector.py
import pytest
from rd_mcp.detectors.drawcall import DrawCallDetector
from rd_mcp.models import Issue, IssueSeverity

def test_detect_excessive_draw_calls():
    detector = DrawCallDetector(threshold={"max_draw_calls": 100})
    issues = detector.detect_excessive_draw_calls(draw_call_count=150)
    assert len(issues) == 1
    assert issues[0].type == "excessive_draw_calls"
    assert issues[0].severity == IssueSeverity.CRITICAL
    assert "150" in issues[0].description

def test_no_issue_when_under_threshold():
    detector = DrawCallDetector(threshold={"max_draw_calls": 1000})
    issues = detector.detect_excessive_draw_calls(draw_call_count=500)
    assert len(issues) == 0
