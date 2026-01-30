# rd_mcp/tests/test_integration.py
"""Integration tests for the complete RenderDoc MCP workflow."""
import pytest
from pathlib import Path
from rd_mcp.html_parser import HTMLParser
from rd_mcp.analyzer import Analyzer
from rd_mcp.models import ReportSummary


class TestIntegration:
    """Integration tests for end-to-end workflows."""

    def test_full_analysis_workflow(self, tmp_path):
        """Test complete workflow from HTML parsing to analysis."""
        # Create a realistic HTML report fixture
        report_dir = tmp_path / "renderdoc_report"
        report_dir.mkdir()

        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>RenderDoc Capture - OpenGL Test</title>
        </head>
        <body>
            <h1>Frame Capture</h1>
            <p>Total: 1250 draw calls</p>
            <p>15 shaders</p>
        </body>
        </html>
        """
        (report_dir / "index.html").write_text(html_content, encoding="utf-8")

        # Step 1: Parse HTML report
        parser = HTMLParser(str(report_dir))
        summary = parser.extract_summary()

        assert summary.api_type == "OpenGL"
        assert summary.total_draw_calls == 1250
        assert summary.total_shaders == 15
        assert summary.frame_count == 1

        # Step 2: Analyze with detector
        analyzer = Analyzer()
        shaders = {
            "vertex_shader_main": {"instructions": 100},
            "fragment_shader_heavy": {"instructions": 800},
            "fragment_shader_light": {"instructions": 50}
        }
        resources = [
            {"name": "albedo_map", "width": 2048, "height": 2048},
            {"name": "normal_map", "width": 1024, "height": 1024},
            {"name": "shadow_map", "width": 8192, "height": 8192}
        ]

        result = analyzer.analyze(summary, shaders, resources)

        # Step 3: Verify results
        assert result.summary == summary
        assert len(result.issues["critical"]) == 1  # Excessive draw calls
        assert result.issues["critical"][0].type == "excessive_draw_calls"

        assert len(result.issues["warnings"]) == 2  # Expensive shader + large texture
        warning_types = {issue.type for issue in result.issues["warnings"]}
        assert "expensive_shader" in warning_types
        assert "large_texture" in warning_types

        assert result.metrics["total_issues"] == 3
        assert result.metrics["critical_count"] == 1
        assert result.metrics["warning_count"] == 2
        assert result.metrics["api_type"] == "OpenGL"

    def test_clean_report_workflow(self, tmp_path):
        """Test workflow with a report that has no issues."""
        # Create a clean HTML report
        report_dir = tmp_path / "clean_report"
        report_dir.mkdir()

        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>RenderDoc Capture - Vulkan Optimized</title>
        </head>
        <body>
            <h1>Performance Capture</h1>
            <p>Draw calls: 350</p>
            <p>Shaders: 8</p>
        </body>
        </html>
        """
        (report_dir / "index.html").write_text(html_content, encoding="utf-8")

        # Parse and analyze
        parser = HTMLParser(str(report_dir))
        summary = parser.extract_summary()

        analyzer = Analyzer()
        result = analyzer.analyze(summary, {}, [])

        # Verify no issues detected
        assert len(result.issues["critical"]) == 0
        assert len(result.issues["warnings"]) == 0
        assert len(result.issues["suggestions"]) == 0
        assert result.metrics["total_issues"] == 0

    def test_custom_config_workflow(self, tmp_path):
        """Test workflow with custom configuration."""
        import json

        # Create custom config
        config_path = tmp_path / "custom_config.json"
        config_data = {
            "thresholds": {
                "max_draw_calls": 100,
                "expensive_shader_instructions": 200,
                "large_texture_size": 1024
            }
        }
        config_path.write_text(json.dumps(config_data))

        # Create report with moderate values
        report_dir = tmp_path / "moderate_report"
        report_dir.mkdir()

        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>RenderDoc - DirectX 12</title>
        </head>
        <body>
            <p>Total: 150 draw calls</p>
            <p>5 shaders</p>
        </body>
        </html>
        """
        (report_dir / "index.html").write_text(html_content, encoding="utf-8")

        # Parse with custom config
        parser = HTMLParser(str(report_dir))
        summary = parser.extract_summary()

        analyzer = Analyzer(config_path=str(config_path))
        shaders = {"shader": {"instructions": 250}}
        resources = [{"name": "tex", "width": 2048, "height": 2048}]

        result = analyzer.analyze(summary, shaders, resources)

        # With strict thresholds, should detect issues
        assert len(result.issues["critical"]) == 1  # 150 > 100
        assert len(result.issues["warnings"]) == 2  # shader and texture
        assert result.metrics["thresholds"]["max_draw_calls"] == 100
        assert result.metrics["thresholds"]["expensive_shader_instructions"] == 200

    def test_error_handling_workflow(self, tmp_path):
        """Test error handling in the workflow."""
        # Test with non-existent directory
        with pytest.raises(FileNotFoundError):
            parser = HTMLParser(str(tmp_path / "nonexistent"))

        # Test with directory without index.html
        empty_dir = tmp_path / "empty_dir"
        empty_dir.mkdir()

        parser = HTMLParser(str(empty_dir))
        with pytest.raises(FileNotFoundError):
            parser.extract_summary()

    def test_realistic_vulkan_report(self, tmp_path):
        """Test with a more realistic Vulkan report structure."""
        report_dir = tmp_path / "vulkan_report"
        report_dir.mkdir()

        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Vulkan Capture - Heavy Scene</title>
        </head>
        <body>
            <div id="header">
                <h1>RenderDoc Capture</h1>
                <span class="api">Vulkan 1.3</span>
            </div>
            <div class="frame-stats">
                <p>2847 draw calls</p>
                <p>42 shader programs</p>
                <p>Frame Time: 16.7ms</p>
            </div>
        </body>
        </html>
        """
        (report_dir / "index.html").write_text(html_content, encoding="utf-8")

        # Parse
        parser = HTMLParser(str(report_dir))
        summary = parser.extract_summary()

        assert summary.api_type == "Vulkan"
        assert summary.total_draw_calls == 2847
        assert summary.total_shaders == 42

        # Analyze with multiple issues
        analyzer = Analyzer()
        shaders = {
            "vs_main": {"instructions": 150},
            "ps_complex": {"instructions": 1200},
            "cs_compute": {"instructions": 850},
            "ps_simple": {"instructions": 80}
        }
        resources = [
            {"name": "gbuffer0", "width": 3840, "height": 2160},
            {"name": "gbuffer1", "width": 3840, "height": 2160},
            {"name": "depth", "width": 3840, "height": 2160},
            {"name": "shadowmap", "width": 8192, "height": 8192},
            {"name": "environment", "width": 512, "height": 512}
        ]

        result = analyzer.analyze(summary, shaders, resources)

        # Verify comprehensive analysis
        assert len(result.issues["critical"]) == 1  # Excessive draw calls
        assert len(result.issues["warnings"]) == 3  # 2 expensive shaders + 1 large texture (8192x8192)
        assert result.metrics["total_issues"] == 4
        assert result.metrics["shader_count"] == 42

    def test_metrics_completeness(self, tmp_path):
        """Test that all metrics are properly computed."""
        report_dir = tmp_path / "metrics_test"
        report_dir.mkdir()

        html_content = """
        <!DOCTYPE html>
        <html>
        <head><title>OpenGL Test</title></head>
        <body>
            <p>Draw calls: 500</p>
            <p>Shaders: 10</p>
        </body>
        </html>
        """
        (report_dir / "index.html").write_text(html_content, encoding="utf-8")

        parser = HTMLParser(str(report_dir))
        summary = parser.extract_summary()

        analyzer = Analyzer()
        result = analyzer.analyze(summary, {}, [])

        # Check all expected metrics
        expected_keys = [
            "total_issues",
            "critical_count",
            "warning_count",
            "suggestion_count",
            "api_type",
            "draw_calls",
            "shader_count",
            "frame_count",
            "thresholds"
        ]

        for key in expected_keys:
            assert key in result.metrics, f"Missing metric: {key}"

        # Check threshold structure
        assert "max_draw_calls" in result.metrics["thresholds"]
        assert "expensive_shader_instructions" in result.metrics["thresholds"]
        assert "large_texture_size" in result.metrics["thresholds"]
