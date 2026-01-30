# rd_mcp/tests/test_models.py
import pytest
import json
from pydantic import ValidationError
from rd_mcp.models import Issue, IssueSeverity, AnalysisResult, ReportSummary

def test_issue_creation():
    issue = Issue(
        type="excessive_draw_calls",
        severity=IssueSeverity.CRITICAL,
        description="Draw call 数量过多 (1234)，建议合并",
        location="Frame 0"
    )
    assert issue.type == "excessive_draw_calls"
    assert issue.severity == IssueSeverity.CRITICAL

def test_analysis_result_creation():
    result = AnalysisResult(
        summary=ReportSummary(
            api_type="OpenGL",
            total_draw_calls=1234,
            total_shaders=56,
            frame_count=1
        ),
        issues={
            "critical": [
                Issue(
                    type="excessive_draw_calls",
                    severity=IssueSeverity.CRITICAL,
                    description="Draw call 数量过多",
                    location="Frame 0"
                )
            ],
            "warnings": [],
            "suggestions": []
        },
        metrics={
            "draw_call_count": 1234,
            "avg_shader_instructions": 234
        }
    )
    assert len(result.issues["critical"]) == 1
    assert result.summary.total_draw_calls == 1234

def test_issue_validation_error_missing_location():
    """Test that Issue model validates required fields."""
    with pytest.raises(ValidationError):
        Issue(type="test", severity=IssueSeverity.CRITICAL, description="test")

def test_issue_default_impact():
    """Test that impact field defaults to 'medium'."""
    issue = Issue(type="test", severity=IssueSeverity.CRITICAL,
                  description="test", location="test")
    assert issue.impact == "medium"

def test_json_serialization():
    """Test JSON serialization works correctly."""
    issue = Issue(type="test", severity=IssueSeverity.CRITICAL,
                  description="test", location="test")
    json_str = issue.model_dump_json()
    assert isinstance(json_str, str)
    # Verify it can be deserialized back
    data = json.loads(json_str)
    assert data["impact"] == "medium"

def test_all_severity_levels():
    """Test all severity enum values work."""
    for severity in IssueSeverity:
        issue = Issue(type="test", severity=severity,
                      description="test", location="test")
        assert issue.severity == severity
