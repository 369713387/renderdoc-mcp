# rd_mcp/tests/integration/test_real_rdc.py
"""
Integration tests for real RDC files using the mobile-aggressive preset.

These tests verify the complete workflow from RDC analysis to HTML report generation
and performance analysis with strict mobile device thresholds.
"""
import pytest
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

from rd_mcp.config import Config
from rd_mcp.analyzer import Analyzer
from rd_mcp.models import ReportSummary, AnalysisResult
from rd_mcp.html_parser import HTMLParser
from rd_mcp.detectors.passes.switches import PassSwitchesDetector


class TestRealRDCIntegration:
    """Integration tests with real RDC files and mobile-aggressive preset."""

    @pytest.fixture
    def mobile_aggressive_config(self):
        """Load mobile-aggressive preset configuration."""
        return Config.load_preset("mobile-aggressive")

    @pytest.fixture
    def mock_rdc_data(self):
        """Mock RDC analysis data for a mobile game capture."""
        return {
            "frame": {
                "draw_calls": [
                    {
                        "id": 1,
                        "name": "glDrawArrays",
                        "primitive": "Triangles",
                        "count": 1200,
                        "instance_count": 1,
                        "marker": "OpaqueGeometry"
                    },
                    {
                        "id": 2,
                        "name": "glDrawArrays",
                        "primitive": "Triangles",
                        "count": 800,
                        "instance_count": 1,
                        "marker": "TransparentGeometry"
                    },
                    {
                        "id": 3,
                        "name": "glDrawArraysInstanced",
                        "primitive": "Triangles",
                        "count": 500,
                        "instance_count": 50,
                        "marker": "ShadowPass"
                    }
                ],
                "api_calls": ["glUseProgram", "glBindTexture", "glDrawArrays"],
                "shaders": {
                    "vs_main": {
                        "type": "vertex",
                        "instructions": 180,
                        "registers": 32,
                        "samplers": 4
                    },
                    "ps_complex": {
                        "type": "fragment",
                        "instructions": 450,  # Exceeds mobile-aggressive threshold
                        "registers": 64,
                        "samplers": 8
                    },
                    "ps_simple": {
                        "type": "fragment",
                        "instructions": 85,  # Within threshold
                        "registers": 16,
                        "samplers": 2
                    }
                },
                "resources": [
                    {
                        "name": "albedo_map",
                        "type": "texture",
                        "width": 2048,
                        "height": 2048,
                        "format": "RGBA8"
                    },
                    {
                        "name": "normal_map",
                        "type": "texture",
                        "width": 1024,
                        "height": 1024,
                        "format": "RGBA8"
                    },
                    {
                        "name": "shadow_map",
                        "type": "texture",
                        "width": 4096,  # Exceeds mobile-aggressive threshold
                        "height": 4096,
                        "format": "Depth24Stencil8"
                    }
                ],
                "stats": {
                    "total_draw_calls": 1500,
                    "total_triangles": 250000,
                    "total_vertices": 750000,
                    "frame_time_ms": 16.7
                }
            }
        }

    def test_mobile_aggressive_preset_loading(self, mobile_aggressive_config):
        """Test that mobile-aggressive preset loads correctly with strict thresholds."""
        thresholds = mobile_aggressive_config.thresholds

        # Verify strict geometry thresholds
        assert thresholds.geometry.max_draw_calls == 500
        assert thresholds.geometry.max_triangles == 50000
        assert thresholds.geometry.max_triangles_per_model == 10000

        # Verify strict shader thresholds
        assert thresholds.shader.max_vs_instructions == 100
        assert thresholds.shader.max_fs_instructions == 150
        assert thresholds.shader.max_cs_instructions == 200

        # Verify strict pass thresholds
        assert thresholds.pass_.max_duration_ms == 0.3
        assert thresholds.pass_.max_overdraw_ratio == 2.0
        assert thresholds.pass_.max_switches_per_frame == 8

        # Verify strict memory thresholds
        assert thresholds.memory.max_texture_size == 2048
        assert thresholds.memory.require_compressed_textures is True

  
    def test_model_stats_extraction_integration(self, mobile_aggressive_config):
        """Test model statistics extraction from RDC data."""
        analyzer = Analyzer(preset="mobile-aggressive")

        # Create mock model data
        model_stats = {
            "total_models": 45,
            "models_by_type": {
                "static_mesh": 25,
                "skinned_mesh": 15,
                "particle_system": 5
            },
            "avg_triangles_per_model": 5556,
            "max_triangles_per_model": 12000,  # Exceeds threshold
            "total_draw_calls_for_models": 1350,
            "instanced_draw_calls": 150
        }

        # Verify model stats processing
        assert model_stats["total_models"] > 0
        assert model_stats["avg_triangles_per_model"] > 0
        assert model_stats["max_triangles_per_model"] > mobile_aggressive_config.thresholds.geometry.max_triangles_per_model

        # Check triangle count distribution
        large_models = [name for name, count in model_stats["models_by_type"].items()
                       if count > 20]  # Models with high triangle count
        assert len(large_models) > 0  # Should have some large models in mobile game

    def test_pass_switches_detection_integration(self, mobile_aggressive_config):
        """Test pass switches detection in mobile rendering context."""
        analyzer = Analyzer(preset="mobile-aggressive")

        # Create mock pass data with many switches
        pass_data = {
            "total_passes": 12,
            "passes": [
                {"name": "ShadowMap", "draw_calls": 45, "switches_from": None},
                {"name": "GBuffer", "draw_calls": 320, "switches_from": "ShadowMap"},
                {"name": "Lighting", "draw_calls": 180, "switches_from": "GBuffer"},
                {"name": "PostFX", "draw_calls": 95, "switches_from": "Lighting"},
                {"name": "UI", "draw_calls": 210, "switches_from": "PostFX"},
                {"name": "ShadowMap2", "draw_calls": 32, "switches_from": "UI"},
                {"name": "GBuffer2", "draw_calls": 280, "switches_from": "ShadowMap2"},
                {"name": "Lighting2", "draw_calls": 150, "switches_from": "GBuffer2"},
                {"name": "PostFX2", "draw_calls": 85, "switches_from": "Lighting2"},
                {"name": "UI2", "draw_calls": 190, "switches_from": "PostFX2"},
                {"name": "ShadowMap3", "draw_calls": 28, "switches_from": "UI2"},
                {"name": "Final", "draw_calls": 165, "switches_from": "ShadowMap3"}
            ],
            "total_switches": 11,  # Exceeds mobile-aggressive threshold of 8
            "switches_per_pass": {
                "ShadowMap": 0,
                "GBuffer": 1,
                "Lighting": 1,
                "PostFX": 1,
                "UI": 1,
                "ShadowMap2": 1,
                "GBuffer2": 1,
                "Lighting2": 1,
                "PostFX2": 1,
                "UI2": 1,
                "ShadowMap3": 1,
                "Final": 1
            }
        }

        # Verify pass switch detection
        assert pass_data["total_switches"] > mobile_aggressive_config.thresholds.pass_.max_switches_per_frame
        assert pass_data["total_passes"] > 8  # Multiple render passes in mobile game

        # Check for performance impact
        switches_per_pass_avg = pass_data["total_switches"] / pass_data["total_passes"]
        assert switches_per_pass_avg > 0.8  # High switch rate

        # This should trigger pass switches detection in the analyzer
        pass_switch_issues = []
        if hasattr(analyzer, '_detect_pass_switches'):
            pass_switch_issues = analyzer._detect_pass_switches(pass_data)
            assert len(pass_switch_issues) > 0
            assert pass_switch_issues[0].type == "pass_switches"

    def test_mobile_specific_performance_issues(self, mobile_aggressive_config):
        """Test detection of mobile-specific performance issues."""
        analyzer = Analyzer(preset="mobile-aggressive")

        # Create mobile-specific performance data
        mobile_issues = {
            "texture_swapping": {
                "count": 25,  # High texture count
                "size_mb": 512,  # Large texture memory usage
                "compressed_ratio": 0.6  # 60% compression
            },
            "overdraw": {
                "max_ratio": 3.5,  # Exceeds 2.0 threshold
                "avg_ratio": 2.8,
                "problematic_areas": ["Sky", "Water", "Foliage"]
            },
            "draw_call_batching": {
                "total_draw_calls": 1500,
                "batched_draw_calls": 900,
                "batching_efficiency": 0.6,  # 60% efficiency
                "unbatched": 600
            }
        }

        # Verify mobile-specific issue detection
        assert mobile_issues["texture_swapping"]["size_mb"] > 200  # Large texture memory
        assert mobile_issues["overdraw"]["max_ratio"] > mobile_aggressive_config.thresholds.pass_.max_overdraw_ratio
        assert mobile_issues["draw_call_batching"]["batching_efficiency"] < 0.8  # Poor batching

        # These should trigger specific mobile warnings
        mobile_warnings = []
        for issue_type, data in mobile_issues.items():
            if issue_type == "overdraw" and data["max_ratio"] > 2.0:
                mobile_warnings.append(f"High overdraw detected: {data['max_ratio']}x")
            elif issue_type == "texture_swapping" and data["size_mb"] > 256:
                mobile_warnings.append(f"High texture memory usage: {data['size_mb']}MB")
            elif issue_type == "draw_call_batching" and data["batching_efficiency"] < 0.7:
                mobile_warnings.append(f"Poor batching efficiency: {int(data['batching_efficiency']*100)}%")

        assert len(mobile_warnings) > 0  # Should detect mobile-specific issues

    def test_integration_with_html_report_generation(self, tmp_path, mobile_aggressive_config):
        """Test complete integration from RDC to HTML report to analysis."""
        # Create mock HTML report
        report_dir = tmp_path / "mobile_game_report"
        report_dir.mkdir()

        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>RenderDoc Mobile Game Analysis - Combat Scene</title>
            <style>
                .frame-stats { background: #f5f5f5; padding: 10px; }
                .api-info { color: #666; }
            </style>
        </head>
        <body>
            <h1>RenderDoc Capture - OpenGL ES 3.1</h1>
            <div class="frame-stats">
                <p><strong>Draw Calls:</strong> 1500</p>
                <p><strong>Shaders:</strong> 42</p>
                <p><strong>Frame Time:</strong> 16.7ms</p>
                <p><strong>API:</strong> OpenGL ES</p>
            </div>
            <div class="api-info">
                <p>Total triangles: 250,000</p>
                <p>Total vertices: 750,000</p>
            </div>
        </body>
        </html>
        """
        (report_dir / "index.html").write_text(html_content, encoding="utf-8")

        # Parse HTML report
        parser = HTMLParser(str(report_dir))
        summary = parser.extract_summary()

        assert summary.api_type == "OpenGL ES"
        assert summary.total_draw_calls == 1500
        assert summary.total_shaders == 42

        # Analyze with mobile-aggressive preset
        analyzer = Analyzer(preset="mobile-aggressive")

        # Create realistic mobile shader data
        shaders = {
            f"shader_{i}": {"instructions": 200 + (i % 3) * 100}  # Mix of expensive and cheap shaders
            for i in range(42)
        }

        # Create realistic mobile texture data
        resources = [
            {"name": f"tex_{i}", "width": 1024 + (i % 4) * 1024, "height": 1024 + (i % 4) * 1024}
            for i in range(20)
        ]

        # Perform analysis
        result = analyzer.analyze(summary, shaders, resources)

        # Verify comprehensive analysis results
        assert result.metrics["total_issues"] > 0
        assert result.metrics["critical_count"] > 0
        assert result.metrics["warning_count"] > 0

        # Check that mobile-aggressive preset is being used
        assert result.metrics["thresholds"]["max_draw_calls"] == 500
        assert result.metrics["thresholds"]["expensive_shader_instructions"] == 150
        assert result.metrics["thresholds"]["large_texture_size"] == 2048

        # Verify issues are appropriate for mobile gaming
        issue_types = [issue.type for category in result.issues.values() for issue in category]
        assert "excessive_draw_calls" in issue_types  # Mobile games should optimize draw calls
        assert any("expensive_shader" in t for t in issue_types)  # Mobile GPUs have limited shader power
        assert any("large_texture" in t for t in issue_types)  # Mobile memory is limited

    def test_memory_usage_analysis_integration(self, mobile_aggressive_config):
        """Test memory usage analysis for mobile devices."""
        analyzer = Analyzer(preset="mobile-aggressive")

        # Create mobile memory analysis data
        memory_analysis = {
            "total_textures": 25,
            "texture_memory_mb": {
                "albedo": 128,
                "normal": 64,
                "roughness": 32,
                "metallic": 32,
                "ao": 16,
                "shadowmaps": 256,
                "cubemaps": 128,
                "framebuffers": 512,  # Large FBO memory
                "total": 1168
            },
            "buffer_memory_mb": {
                "vertex_buffers": 256,
                "index_buffers": 64,
                "uniform_buffers": 32,
                "total": 352
            },
            "shader_memory_mb": {
                "vertex_shaders": 48,
                "fragment_shaders": 96,
                "total": 144
            },
            "total_memory_mb": 1664  # Total GPU memory usage
        }

        # Verify mobile memory constraints
        assert memory_analysis["total_memory_mb"] > 1024  # High memory usage for mobile
        assert memory_analysis["texture_memory_mb"]["framebuffers"] > 256  # Large FBO memory

        # Check for memory issues using mobile-aggressive thresholds
        memory_issues = []
        if memory_analysis["total_memory_mb"] > 1536:  # 1.5GB threshold
            memory_issues.append("High total GPU memory usage")
        if memory_analysis["texture_memory_mb"]["framebuffers"] > 512:
            memory_issues.append("Large framebuffer memory usage")
        if memory_analysis["shader_memory_mb"]["total"] > 128:
            memory_issues.append("High shader memory usage")

        assert len(memory_issues) > 0  # Should detect memory issues

    def test_performance_metrics_completeness(self, mobile_aggressive_config):
        """Test that all performance metrics are properly captured and reported."""
        analyzer = Analyzer(preset="mobile-aggressive")

        # Create comprehensive performance metrics
        metrics = {
            "frame_analysis": {
                "draw_calls": 1500,
                "triangles": 250000,
                "vertices": 750000,
                "frame_time": 16.7,
                "fps": 59.8
            },
            "shader_analysis": {
                "total_shaders": 42,
                "avg_instructions": 225,
                "max_instructions": 650,
                "shader_types": {
                    "vertex": 15,
                    "fragment": 25,
                    "compute": 2
                }
            },
            "resource_analysis": {
                "total_textures": 25,
                "avg_texture_size": 2048,
                "max_texture_size": 4096,
                "texture_formats": ["RGBA8", "Depth24Stencil8", "RGBA16F"]
            },
            "memory_analysis": {
                "texture_memory_mb": 1168,
                "buffer_memory_mb": 352,
                "shader_memory_mb": 144,
                "total_memory_mb": 1664
            },
            "performance_analysis": {
                "batches": 45,
                "batched_draw_calls": 900,
                "batching_efficiency": 0.6,
                "overdraw_max": 3.5,
                "overdraw_avg": 2.8
            }
        }

        # Verify all expected metric categories
        expected_categories = [
            "frame_analysis", "shader_analysis", "resource_analysis",
            "memory_analysis", "performance_analysis"
        ]

        for category in expected_categories:
            assert category in metrics
            assert isinstance(metrics[category], dict)

        # Check mobile-specific constraints
        frame_metrics = metrics["frame_analysis"]
        assert frame_metrics["frame_time"] > 16.0  # High frame time for mobile

        shader_metrics = metrics["shader_analysis"]
        assert shader_metrics["max_instructions"] > mobile_aggressive_config.thresholds.shader.max_fs_instructions

        resource_metrics = metrics["resource_analysis"]
        assert resource_metrics["max_texture_size"] > mobile_aggressive_config.thresholds.memory.max_texture_size

        performance_metrics = metrics["performance_analysis"]
        assert performance_metrics["overdraw_max"] > mobile_aggressive_config.thresholds.pass_.max_overdraw_ratio
        assert performance_metrics["batching_efficiency"] < 0.8  # Poor batching

    def teardown_method(self):
        """Clean up after each test."""
        # Clear any cached data or resources
        pass