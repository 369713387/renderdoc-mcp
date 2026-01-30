# rd_mcp/tests/test_analyzer.py
import pytest
from rd_mcp.analyzer import Analyzer
from rd_mcp.models import ReportSummary, IssueSeverity


class TestAnalyzer:
    """Test suite for the Analyzer class."""

    def test_init_default_config(self):
        """Test analyzer initialization with default config."""
        analyzer = Analyzer()
        assert analyzer.config is not None
        assert analyzer.drawcall_detector is not None
        assert analyzer.shader_detector is not None
        assert analyzer.resource_detector is not None

    def test_init_custom_config(self, tmp_path):
        """Test analyzer initialization with custom config."""
        import json
        config_path = tmp_path / "custom_config.json"
        config_data = {
            "thresholds": {
                "max_draw_calls": 500,
                "expensive_shader_instructions": 300,
                "large_texture_size": 2048
            }
        }
        config_path.write_text(json.dumps(config_data))

        analyzer = Analyzer(config_path=str(config_path))
        assert analyzer.config.thresholds.max_draw_calls == 500
        assert analyzer.config.thresholds.expensive_shader_instructions == 300
        assert analyzer.config.thresholds.large_texture_size == 2048

    def test_analyze_no_issues(self):
        """Test analysis with no issues detected."""
        analyzer = Analyzer()
        summary = ReportSummary(
            api_type="OpenGL",
            total_draw_calls=100,
            total_shaders=5,
            frame_count=1
        )
        shaders = {
            "vertex_shader": {"instructions": 50},
            "fragment_shader": {"instructions": 100}
        }
        resources = [
            {"name": "texture1", "width": 512, "height": 512}
        ]

        result = analyzer.analyze(summary, shaders, resources)

        assert result.summary == summary
        assert len(result.issues["critical"]) == 0
        assert len(result.issues["warnings"]) == 0
        assert len(result.issues["suggestions"]) == 0
        assert "total_issues" in result.metrics
        assert result.metrics["total_issues"] == 0

    def test_analyze_with_drawcall_issue(self):
        """Test analysis detecting excessive draw calls."""
        analyzer = Analyzer()
        summary = ReportSummary(
            api_type="Vulkan",
            total_draw_calls=2000,
            total_shaders=5,
            frame_count=1
        )
        shaders = {}
        resources = []

        result = analyzer.analyze(summary, shaders, resources)

        assert len(result.issues["critical"]) == 1
        assert result.issues["critical"][0].type == "excessive_draw_calls"
        assert result.issues["critical"][0].severity == IssueSeverity.CRITICAL
        assert "2000" in result.issues["critical"][0].description
        assert result.metrics["total_issues"] == 1

    def test_analyze_with_shader_issues(self):
        """Test analysis detecting expensive shaders."""
        analyzer = Analyzer()
        summary = ReportSummary(
            api_type="OpenGL",
            total_draw_calls=100,
            total_shaders=3,
            frame_count=1
        )
        shaders = {
            "expensive_vertex": {"instructions": 800},
            "cheap_fragment": {"instructions": 100}
        }
        resources = []

        result = analyzer.analyze(summary, shaders, resources)

        assert len(result.issues["warnings"]) == 1
        assert result.issues["warnings"][0].type == "expensive_shader"
        assert "expensive_vertex" in result.issues["warnings"][0].location
        assert result.metrics["total_issues"] == 1

    def test_analyze_with_texture_issues(self):
        """Test analysis detecting large textures."""
        analyzer = Analyzer()
        summary = ReportSummary(
            api_type="Vulkan",
            total_draw_calls=100,
            total_shaders=2,
            frame_count=1
        )
        shaders = {}
        resources = [
            {"name": "huge_texture", "width": 8192, "height": 8192},
            {"name": "normal_texture", "width": 1024, "height": 1024}
        ]

        result = analyzer.analyze(summary, shaders, resources)

        assert len(result.issues["warnings"]) == 1
        assert result.issues["warnings"][0].type == "large_texture"
        assert "huge_texture" in result.issues["warnings"][0].location
        assert result.metrics["total_issues"] == 1

    def test_analyze_multiple_issues(self):
        """Test analysis with multiple types of issues."""
        analyzer = Analyzer()
        summary = ReportSummary(
            api_type="OpenGL",
            total_draw_calls=1500,
            total_shaders=4,
            frame_count=1
        )
        shaders = {
            "heavy_shader": {"instructions": 1000}
        }
        resources = [
            {"name": "big_tex", "width": 5000, "height": 5000}
        ]

        result = analyzer.analyze(summary, shaders, resources)

        assert len(result.issues["critical"]) == 1
        assert len(result.issues["warnings"]) == 2
        assert result.metrics["total_issues"] == 3
        assert result.metrics["critical_count"] == 1
        assert result.metrics["warning_count"] == 2

    def test_analyze_metrics_completeness(self):
        """Test that all expected metrics are present."""
        analyzer = Analyzer()
        summary = ReportSummary(
            api_type="Vulkan",
            total_draw_calls=100,
            total_shaders=2,
            frame_count=1
        )
        shaders = {}
        resources = []

        result = analyzer.analyze(summary, shaders, resources)

        expected_metrics = [
            "total_issues",
            "critical_count",
            "warning_count",
            "suggestion_count",
            "api_type",
            "draw_calls",
            "shader_count",
            "frame_count"
        ]
        for metric in expected_metrics:
            assert metric in result.metrics, f"Missing metric: {metric}"
