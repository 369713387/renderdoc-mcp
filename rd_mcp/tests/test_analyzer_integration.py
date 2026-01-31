# rd_mcp/tests/test_analyzer_integration.py
"""Integration tests for Analyzer with new detectors.

Tests the integration of geometry and pass detectors into the main Analyzer class.
"""
import pytest
from rd_mcp.analyzer import Analyzer
from rd_mcp.models import ReportSummary, IssueSeverity, ModelStats, PassSwitchInfo
from rd_mcp.rdc_analyzer_cmd import DrawCallInfo, PassInfo


class TestAnalyzerIntegration:
    """Test suite for analyzer integration with new detectors."""

    def test_init_with_preset(self):
        """Test analyzer initialization with preset configuration."""
        analyzer = Analyzer(preset="mobile-balanced")
        assert analyzer.config is not None
        assert analyzer.triangle_count_detector is not None
        assert analyzer.model_stats_detector is not None
        assert analyzer.pass_duration_detector is not None
        assert analyzer.pass_switches_detector is not None

    def test_init_without_preset(self):
        """Test analyzer initialization without preset (default config)."""
        analyzer = Analyzer()
        assert analyzer.config is not None
        # Should still have detectors initialized with default thresholds
        assert hasattr(analyzer, 'triangle_count_detector')
        assert hasattr(analyzer, 'model_stats_detector')
        assert hasattr(analyzer, 'pass_duration_detector')
        assert hasattr(analyzer, 'pass_switches_detector')

    def test_analyze_with_all_detectors(self):
        """Test full analysis workflow with all detectors."""
        analyzer = Analyzer(preset="mobile-balanced")

        summary = ReportSummary(
            api_type="OpenGL",
            total_draw_calls=150,
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

        # Create mock draw calls
        draws = self._create_test_draws()

        # Create mock passes
        passes = self._create_test_passes()

        result = analyzer.analyze(
            summary=summary,
            shaders=shaders,
            resources=resources,
            draws=draws,
            passes=passes
        )

        # Should have model_stats populated
        assert result.model_stats is not None
        assert isinstance(result.model_stats, dict)
        assert len(result.model_stats) > 0

        # Should have pass_switches populated
        assert result.pass_switches is not None
        assert isinstance(result.pass_switches, PassSwitchInfo)

        # Verify model_stats structure
        for model_name, stats in result.model_stats.items():
            assert isinstance(stats, ModelStats)
            assert stats.name == model_name
            assert stats.draw_calls >= 0
            assert stats.triangle_count >= 0
            assert stats.vertex_count >= 0
            assert isinstance(stats.passes, list)

    def test_analyze_with_none_draws_and_passes(self):
        """Test analysis when draws and passes are None."""
        analyzer = Analyzer()

        summary = ReportSummary(
            api_type="Vulkan",
            total_draw_calls=100,
            total_shaders=3,
            frame_count=1
        )

        shaders = {}
        resources = []

        # Pass None for draws and passes - should not crash
        result = analyzer.analyze(
            summary=summary,
            shaders=shaders,
            resources=resources,
            draws=None,
            passes=None
        )

        # model_stats should be empty dict
        assert result.model_stats == {}
        # pass_switches should be None
        assert result.pass_switches is None

    def test_model_stats_in_result(self):
        """Test that model_stats are correctly included in result."""
        analyzer = Analyzer()

        summary = ReportSummary(
            api_type="OpenGL",
            total_draw_calls=100,
            total_shaders=2,
            frame_count=1
        )

        shaders = {}
        resources = []

        # Create draws with known markers
        draws = [
            DrawCallInfo(
                draw_id=1,
                event_id=1,
                name="glDrawArrays",
                vertex_count=3000,
                marker="Character"
            ),
            DrawCallInfo(
                draw_id=2,
                event_id=2,
                name="glDrawArrays",
                vertex_count=6000,
                marker="Character"
            ),
            DrawCallInfo(
                draw_id=3,
                event_id=3,
                name="glDrawArrays",
                vertex_count=1500,
                marker="UI"
            ),
        ]

        passes = []

        result = analyzer.analyze(
            summary=summary,
            shaders=shaders,
            resources=resources,
            draws=draws,
            passes=passes
        )

        # Check model_stats
        assert "Character" in result.model_stats
        assert "UI" in result.model_stats

        character_stats = result.model_stats["Character"]
        assert character_stats.name == "Character"
        assert character_stats.draw_calls == 2
        assert character_stats.triangle_count == (3000 + 6000) // 3
        assert character_stats.vertex_count == 9000

        ui_stats = result.model_stats["UI"]
        assert ui_stats.name == "UI"
        assert ui_stats.draw_calls == 1
        assert ui_stats.triangle_count == 1500 // 3

    def test_pass_switches_in_result(self):
        """Test that pass_switches are correctly included in result."""
        analyzer = Analyzer()

        summary = ReportSummary(
            api_type="Vulkan",
            total_draw_calls=50,
            total_shaders=2,
            frame_count=1
        )

        shaders = {}
        resources = []

        # Create draws with marker switches
        draws = []
        for i in range(10):
            draws.append(DrawCallInfo(
                draw_id=i,
                event_id=i,
                name="glDrawArrays",
                vertex_count=1000,
                marker=f"Pass_{i // 2}"  # 5 different passes
            ))

        passes = []

        result = analyzer.analyze(
            summary=summary,
            shaders=shaders,
            resources=resources,
            draws=draws,
            passes=passes
        )

        # Check pass_switches
        assert result.pass_switches is not None
        assert isinstance(result.pass_switches, PassSwitchInfo)
        # Should have detected marker switches
        assert result.pass_switches.marker_switches > 0
        assert result.pass_switches.total > 0

    def test_metrics_include_model_stats(self):
        """Test that metrics include model_stats information."""
        analyzer = Analyzer()

        summary = ReportSummary(
            api_type="OpenGL",
            total_draw_calls=100,
            total_shaders=2,
            frame_count=1
        )

        shaders = {}
        resources = []
        draws = self._create_test_draws()
        passes = self._create_test_passes()

        result = analyzer.analyze(
            summary=summary,
            shaders=shaders,
            resources=resources,
            draws=draws,
            passes=passes
        )

        # Metrics should include model-related stats
        assert "model_count" in result.metrics
        assert result.metrics["model_count"] == len(result.model_stats)

    def test_detector_error_handling(self):
        """Test that detector errors are handled gracefully."""
        analyzer = Analyzer()

        summary = ReportSummary(
            api_type="OpenGL",
            total_draw_calls=100,
            total_shaders=2,
            frame_count=1
        )

        shaders = {}
        resources = []

        # Pass invalid data that might cause detector errors
        draws = [DrawCallInfo(
            draw_id=1,
            event_id=1,
            name="glDrawArrays",
            vertex_count=-1,  # Invalid vertex count
            marker="Test"
        )]

        passes = []

        # Should not crash, but may collect errors
        result = analyzer.analyze(
            summary=summary,
            shaders=shaders,
            resources=resources,
            draws=draws,
            passes=passes
        )

        # Result should still be valid
        assert result.summary == summary

    def test_excessive_triangles_detection(self):
        """Test that excessive triangles are detected."""
        analyzer = Analyzer(preset="mobile-balanced")

        summary = ReportSummary(
            api_type="OpenGL",
            total_draw_calls=100,
            total_shaders=2,
            frame_count=1
        )

        shaders = {}
        resources = []

        # Create draws with excessive triangles
        draws = [DrawCallInfo(
            draw_id=1,
            event_id=1,
            name="glDrawArrays",
            vertex_count=300003,  # 100,001 triangles (exceeds default threshold)
            marker="HeavyModel"
        )]

        passes = []

        result = analyzer.analyze(
            summary=summary,
            shaders=shaders,
            resources=resources,
            draws=draws,
            passes=passes
        )

        # Should detect excessive triangles
        triangle_issues = [i for i in result.issues["critical"]
                          if i.type == "excessive_triangles"]
        assert len(triangle_issues) > 0

    def test_slow_pass_detection(self):
        """Test that slow passes are detected."""
        analyzer = Analyzer(preset="mobile-balanced")

        summary = ReportSummary(
            api_type="OpenGL",
            total_draw_calls=100,
            total_shaders=2,
            frame_count=1
        )

        shaders = {}
        resources = []
        draws = []

        # Create a slow pass
        passes = [PassInfo(
            name="ShadowPass",
            draw_calls=[],
            duration_ms=5.0,  # Slow pass
            resolution="1920x1080"
        )]

        result = analyzer.analyze(
            summary=summary,
            shaders=shaders,
            resources=resources,
            draws=draws,
            passes=passes
        )

        # Should detect slow pass
        slow_pass_issues = [i for i in result.issues["critical"]
                           if i.type == "slow_pass"]
        assert len(slow_pass_issues) > 0

    def test_heavy_model_detection(self):
        """Test that heavy models are detected."""
        analyzer = Analyzer(preset="mobile-balanced")

        summary = ReportSummary(
            api_type="OpenGL",
            total_draw_calls=100,
            total_shaders=2,
            frame_count=1
        )

        shaders = {}
        resources = []

        # Create draws with a heavy model
        draws = [DrawCallInfo(
            draw_id=1,
            event_id=1,
            name="glDrawArrays",
            vertex_count=150000,  # 50,000 triangles (exceeds default threshold)
            marker="HeavyModel"
        )]

        passes = []

        result = analyzer.analyze(
            summary=summary,
            shaders=shaders,
            resources=resources,
            draws=draws,
            passes=passes
        )

        # Should detect heavy model
        heavy_model_issues = [i for i in result.issues["warnings"]
                             if i.type == "heavy_model"]
        assert len(heavy_model_issues) > 0

    # Helper methods

    def _create_test_draws(self):
        """Create test draw calls."""
        return [
            DrawCallInfo(
                draw_id=1,
                event_id=1,
                name="glDrawArrays",
                vertex_count=3000,
                marker="Character"
            ),
            DrawCallInfo(
                draw_id=2,
                event_id=2,
                name="glDrawArrays",
                vertex_count=6000,
                marker="Character"
            ),
            DrawCallInfo(
                draw_id=3,
                event_id=3,
                name="glDrawArrays",
                vertex_count=1500,
                marker="UI"
            ),
        ]

    def _create_test_passes(self):
        """Create test render passes."""
        return [
            PassInfo(
                name="Geometry",
                draw_calls=[],
                duration_ms=0.5,
                resolution="1920x1080"
            ),
            PassInfo(
                name="Lighting",
                draw_calls=[],
                duration_ms=0.3,
                resolution="1920x1080"
            ),
        ]
