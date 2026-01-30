# rd_mcp/tests/test_models.py
import pytest
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
