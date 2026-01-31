# rd_mcp/tests/test_report_format.py
"""Test suite for report formatting functions.

This module tests the format_rdc_analysis_result() function to ensure
it includes all required sections.
"""
import pytest
from rd_mcp.server import format_rdc_analysis_result
from rd_mcp.models import (
    AnalysisResult,
    ReportSummary,
    Issue,
    IssueSeverity,
    ModelStats,
    PassSwitchInfo
)
from rd_mcp.rdc_analyzer_cmd import RDCAnalysisData, RDCSummary, PassInfo


class TestReportFormat:
    """Test suite for report formatting."""

    def create_mock_rdc_data(self):
        """Create mock RDC data for testing."""
        from rd_mcp.rdc_analyzer_cmd import DrawCallInfo, ShaderInfo, TextureInfo

        summary = RDCSummary(
            api_type="OpenGL",
            gpu_name="Test GPU",
            total_draw_calls=100,
            total_shaders=5,
            frame_count=1,
            resolution="1920x1080"
        )

        draws = [
            DrawCallInfo(
                draw_id=i,
                event_id=i*10,
                name=f"draw_{i}",
                duration_ns=1000000 * i,  # 1ms * i
                vertex_count=100 * i,
                marker=f"pass_{i % 3}"
            )
            for i in range(1, 11)
        ]

        shaders = {
            "vertex_shader": ShaderInfo(
                name="vertex_shader",
                stage="Vertex",
                instruction_count=100,
                source_length=500
            ),
            "fragment_shader": ShaderInfo(
                name="fragment_shader",
                stage="Fragment",
                instruction_count=200,
                source_length=1000
            )
        }

        textures = [
            TextureInfo(
                resource_id=f"tex_{i}",
                name=f"texture_{i}",
                width=512 * i,
                height=512 * i,
                format="RGBA8"
            )
            for i in range(1, 4)
        ]

        passes = [
            PassInfo(
                name=f"Pass_{i}",
                draw_calls=draws[i*3:(i+1)*3],
                duration_ms=5.0 * i,
                resolution="1920x1080"
            )
            for i in range(3)
        ]

        return RDCAnalysisData(
            summary=summary,
            draws=draws,
            shaders=shaders,
            textures=textures,
            passes=passes
        )

    def create_mock_analysis_result(self, with_model_stats=True, with_pass_switches=True, with_errors=False):
        """Create mock analysis result for testing."""
        summary = ReportSummary(
            api_type="OpenGL",
            total_draw_calls=100,
            total_shaders=5,
            frame_count=1
        )

        issues = {
            "critical": [
                Issue(
                    type="excessive_draw_calls",
                    severity=IssueSeverity.CRITICAL,
                    description="Too many draw calls",
                    location="Frame",
                    impact="high"
                )
            ],
            "warnings": [
                Issue(
                    type="expensive_shader",
                    severity=IssueSeverity.WARNING,
                    description="Shader has too many instructions",
                    location="Shader: heavy_shader",
                    impact="medium"
                )
            ],
            "suggestions": []
        }

        metrics = {
            "total_issues": 2,
            "critical_count": 1,
            "warning_count": 1,
            "suggestion_count": 0,
            "api_type": "OpenGL",
            "draw_calls": 100,
            "shader_count": 5,
            "frame_count": 1
        }

        model_stats = {}
        if with_model_stats:
            model_stats = {
                "model_high_poly": ModelStats(
                    name="model_high_poly",
                    draw_calls=50,
                    triangle_count=100000,
                    vertex_count=150000,
                    passes=["Pass_1", "Pass_2"]
                ),
                "model_low_poly": ModelStats(
                    name="model_low_poly",
                    draw_calls=30,
                    triangle_count=10000,
                    vertex_count=15000,
                    passes=["Pass_1"]
                )
            }

        pass_switches = None
        if with_pass_switches:
            pass_switches = PassSwitchInfo(
                marker_switches=10,
                fbo_switches=5,
                texture_bind_changes=20,
                shader_changes=8,
                total=43
            )

        errors = ["Error 1", "Error 2"] if with_errors else []

        return AnalysisResult(
            summary=summary,
            issues=issues,
            metrics=metrics,
            model_stats=model_stats,
            pass_switches=pass_switches,
            errors=errors
        )

    def test_report_includes_summary_section(self):
        """Test that report includes Summary section."""
        rdc_data = self.create_mock_rdc_data()
        result = self.create_mock_analysis_result()

        output = format_rdc_analysis_result(result, rdc_data)

        assert "## Summary" in output
        assert "API Type: OpenGL" in output
        assert "Draw Calls: 100" in output
        assert "Shaders: 5" in output

    def test_report_includes_issues_section(self):
        """Test that report includes Issues section."""
        rdc_data = self.create_mock_rdc_data()
        result = self.create_mock_analysis_result()

        output = format_rdc_analysis_result(result, rdc_data)

        assert "## Issues Found: 2" in output
        assert "### Critical (1)" in output
        assert "### Warnings (1)" in output
        assert "excessive_draw_calls" in output
        assert "expensive_shader" in output

    def test_report_includes_model_statistics_section(self):
        """Test that report includes Model Statistics section."""
        rdc_data = self.create_mock_rdc_data()
        result = self.create_mock_analysis_result(with_model_stats=True)

        output = format_rdc_analysis_result(result, rdc_data)

        # Check for Model Statistics section
        assert "## Model Statistics" in output
        # Check that models are listed
        assert "model_high_poly" in output
        assert "model_low_poly" in output
        # Check for triangle counts
        assert "100,000" in output or "100000" in output
        assert "10,000" in output or "10000" in output
        # Check for draw calls
        assert "50" in output
        assert "30" in output

    def test_report_model_statistics_sorted_by_triangle_count(self):
        """Test that models are sorted by triangle count (descending)."""
        rdc_data = self.create_mock_rdc_data()
        result = self.create_mock_analysis_result(with_model_stats=True)

        output = format_rdc_analysis_result(result, rdc_data)

        # Find positions of models in output
        high_poly_pos = output.find("model_high_poly")
        low_poly_pos = output.find("model_low_poly")

        # model_high_poly should appear before model_low_poly (higher triangle count)
        assert high_poly_pos > 0
        assert low_poly_pos > 0
        assert high_poly_pos < low_poly_pos

    def test_report_includes_pass_switches_section(self):
        """Test that report includes Pass Switches section."""
        rdc_data = self.create_mock_rdc_data()
        result = self.create_mock_analysis_result(with_pass_switches=True)

        output = format_rdc_analysis_result(result, rdc_data)

        # Check for Pass Switches section
        assert "## Pass Switches" in output
        # Check for detailed breakdown
        assert "Marker switches:" in output
        assert "FBO switches:" in output
        assert "Texture binding changes:" in output
        assert "Shader changes:" in output
        assert "Total:" in output
        # Check for values
        assert "10" in output  # marker_switches
        assert "5" in output   # fbo_switches
        assert "20" in output  # texture_bind_changes
        assert "8" in output   # shader_changes
        assert "43" in output  # total

    def test_report_includes_errors_section_when_present(self):
        """Test that report includes Detection Errors section when errors are present."""
        rdc_data = self.create_mock_rdc_data()
        result = self.create_mock_analysis_result(with_errors=True)

        output = format_rdc_analysis_result(result, rdc_data)

        # Check for Detection Errors section
        assert "## Detection Errors" in output
        assert "Error 1" in output
        assert "Error 2" in output

    def test_report_does_not_include_errors_section_when_empty(self):
        """Test that report doesn't include Detection Errors section when no errors."""
        rdc_data = self.create_mock_rdc_data()
        result = self.create_mock_analysis_result(with_errors=False)

        output = format_rdc_analysis_result(result, rdc_data)

        # Should not have Detection Errors section
        assert "## Detection Errors" not in output

    def test_report_includes_renders_passes_section(self):
        """Test that report includes Render Passes section."""
        rdc_data = self.create_mock_rdc_data()
        result = self.create_mock_analysis_result()

        output = format_rdc_analysis_result(result, rdc_data)

        # Check for Render Passes section
        assert "## Render Passes" in output
        assert "Total passes:" in output
        # Check for pass names
        assert "Pass_0" in output or "Pass_1" in output

    def test_report_includes_top_draw_calls_section(self):
        """Test that report includes Top Draw Calls by GPU Time section."""
        rdc_data = self.create_mock_rdc_data()
        result = self.create_mock_analysis_result()

        output = format_rdc_analysis_result(result, rdc_data)

        # Check for Top Draw Calls section
        assert "## Top Draw Calls by GPU Time" in output
        # Should have some draw calls listed
        assert "draw_" in output
        assert "Duration:" in output

    def test_report_handles_empty_model_stats(self):
        """Test that report handles empty model statistics gracefully."""
        rdc_data = self.create_mock_rdc_data()
        result = self.create_mock_analysis_result(with_model_stats=False)

        output = format_rdc_analysis_result(result, rdc_data)

        # Should still have Model Statistics section but note no data
        assert "## Model Statistics" in output
        assert "No model statistics available" in output or "0 models" in output

    def test_report_handles_none_pass_switches(self):
        """Test that report handles None pass_switches gracefully."""
        rdc_data = self.create_mock_rdc_data()
        result = self.create_mock_analysis_result(with_pass_switches=False)

        output = format_rdc_analysis_result(result, rdc_data)

        # Should not have Pass Switches section if None
        assert "## Pass Switches" not in output

    def test_report_triangle_count_in_summary(self):
        """Test that triangle count is included in Summary section."""
        rdc_data = self.create_mock_rdc_data()
        result = self.create_mock_analysis_result(with_model_stats=True)

        output = format_rdc_analysis_result(result, rdc_data)

        # Check Summary for triangle count
        assert "## Summary" in output
        # Find the line with total triangles
        summary_lines = [line for line in output.split('\n') if 'Triangle' in line or 'triangle' in line]
        assert len(summary_lines) > 0, "No triangle count in summary"
        # Should show total triangles
        assert "110,000" in summary_lines[0] or "110000" in summary_lines[0]

    def test_report_model_stats_top_10_only(self):
        """Test that only top 10 models are shown."""
        rdc_data = self.create_mock_rdc_data()

        # Create 15 models
        model_stats = {
            f"model_{i:02d}": ModelStats(
                name=f"model_{i:02d}",
                draw_calls=1,
                triangle_count=1000 * i,
                vertex_count=1500 * i,
                passes=["Pass_1"]
            )
            for i in range(1, 16)
        }

        result = self.create_mock_analysis_result(with_model_stats=False)
        result.model_stats = model_stats

        output = format_rdc_analysis_result(result, rdc_data)

        # Should only list top 10
        # Count how many model_ entries appear
        model_count = output.count("model_")
        # Should have at most 10 model entries in the model stats section
        assert model_count <= 12  # Allow for section header and some flexibility
