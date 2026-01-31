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


def test_model_stats():
    """Test ModelStats dataclass"""
    from rd_mcp.models import ModelStats
    stats = ModelStats(
        name="Character",
        draw_calls=10,
        triangle_count=5000,
        vertex_count=1500,
        passes=["Geometry", "Shadow"]
    )
    assert stats.name == "Character"
    assert stats.triangle_count == 5000
    assert "Geometry" in stats.passes


def test_pass_switch_info():
    """Test PassSwitchInfo dataclass"""
    from rd_mcp.models import PassSwitchInfo
    info = PassSwitchInfo(
        marker_switches=5,
        fbo_switches=2,
        texture_bind_changes=10,
        shader_changes=3
    )
    assert info.total == 20


def test_analysis_result_with_errors():
    """Test AnalysisResult with errors field"""
    result = AnalysisResult(
        summary=ReportSummary(
            api_type="OpenGL",
            total_draw_calls=100,
            total_shaders=10,
            frame_count=1
        ),
        issues={"critical": [], "warnings": [], "suggestions": []},
        metrics={},
        errors=["test_error"]
    )
    assert len(result.errors) == 1
    assert result.errors[0] == "test_error"


def test_analysis_result_with_model_stats():
    """Test AnalysisResult with model_stats field"""
    from rd_mcp.models import ModelStats
    result = AnalysisResult(
        summary=ReportSummary(
            api_type="Vulkan",
            total_draw_calls=50,
            total_shaders=5,
            frame_count=1
        ),
        issues={"critical": [], "warnings": [], "suggestions": []},
        metrics={},
        model_stats={
            "Character": ModelStats(
                name="Character",
                draw_calls=10,
                triangle_count=5000,
                vertex_count=1500,
                passes=["Geometry"]
            )
        }
    )
    assert "Character" in result.model_stats
    assert result.model_stats["Character"].triangle_count == 5000


def test_analysis_result_with_pass_switches():
    """Test AnalysisResult with pass_switches field"""
    from rd_mcp.models import PassSwitchInfo
    result = AnalysisResult(
        summary=ReportSummary(
            api_type="DirectX 11",
            total_draw_calls=200,
            total_shaders=15,
            frame_count=1
        ),
        issues={"critical": [], "warnings": [], "suggestions": []},
        metrics={},
        pass_switches=PassSwitchInfo(
            marker_switches=5,
            fbo_switches=2,
            texture_bind_changes=10,
            shader_changes=3
        )
    )
    assert result.pass_switches is not None
    assert result.pass_switches.total == 20
