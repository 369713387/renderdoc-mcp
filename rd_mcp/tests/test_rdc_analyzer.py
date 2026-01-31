# rd_mcp/tests/test_rdc_analyzer.py
"""Tests for the RDC analyzer module."""
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, Mock

from rd_mcp.rdc_analyzer import (
    RDCAnalyzer,
    analyze_rdc_file,
    RDCSummary,
    DrawCallInfo,
    ShaderInfo,
    TextureInfo,
    PassInfo,
    RDCAnalysisData
)


class TestRDCAnalyzer:
    """Tests for RDCAnalyzer class."""

    def test_init_without_renderdoc(self):
        """Test that ImportError is raised when RenderDoc is not available."""
        with patch('rd_mcp.rdc_analyzer._RENDERDOC_AVAILABLE', False):
            with patch('rd_mcp.rdc_analyzer.rd', None):
                with pytest.raises(ImportError, match="RenderDoc Python API"):
                    RDCAnalyzer()

    def test_init_with_renderdoc(self):
        """Test successful initialization when RenderDoc is available."""
        with patch('rd_mcp.rdc_analyzer._RENDERDOC_AVAILABLE', True):
            with patch('rd_mcp.rdc_analyzer.rd'):
                analyzer = RDCAnalyzer()
                assert analyzer._controller is None
                assert analyzer._capture is None
                assert analyzer._draw_durations == {}

    @pytest.mark.skipif(
        True,  # Skip by default as it requires actual RDC file
        reason="Requires actual RenderDoc installation and RDC file"
    )
    def test_analyze_file_integration(self):
        """Integration test with actual RDC file (requires RenderDoc)."""
        # This test requires a real RDC file and RenderDoc installation
        # It should be run manually for verification
        pass


class TestRDCSummary:
    """Tests for RDCSummary dataclass."""

    def test_creation(self):
        """Test creating RDCSummary."""
        summary = RDCSummary(
            api_type="Vulkan",
            total_draw_calls=100,
            total_shaders=10,
            frame_count=1
        )
        assert summary.api_type == "Vulkan"
        assert summary.total_draw_calls == 100
        assert summary.total_shaders == 10
        assert summary.frame_count == 1


class TestDrawCallInfo:
    """Tests for DrawCallInfo dataclass."""

    def test_creation(self):
        """Test creating DrawCallInfo."""
        draw = DrawCallInfo(
            draw_id=1,
            event_id=100,
            name="TestDraw",
            gpu_duration_ms=0.5,
            vertex_count=1000,
            instance_count=1,
            marker="TestPass"
        )
        assert draw.draw_id == 1
        assert draw.event_id == 100
        assert draw.name == "TestDraw"
        assert draw.gpu_duration_ms == 0.5
        assert draw.vertex_count == 1000
        assert draw.instance_count == 1
        assert draw.marker == "TestPass"


class TestShaderInfo:
    """Tests for ShaderInfo dataclass."""

    def test_creation(self):
        """Test creating ShaderInfo."""
        shader = ShaderInfo(
            name="test_shader",
            stage="Pixel",
            instruction_count=500,
            binding_count=10,
            uniform_count=5
        )
        assert shader.name == "test_shader"
        assert shader.stage == "Pixel"
        assert shader.instruction_count == 500
        assert shader.binding_count == 10
        assert shader.uniform_count == 5


class TestTextureInfo:
    """Tests for TextureInfo dataclass."""

    def test_creation(self):
        """Test creating TextureInfo."""
        texture = TextureInfo(
            resource_id="12345",
            name="test_texture",
            width=1024,
            height=1024,
            depth=1,
            format="RGBA8",
            mips=1,
            array_size=1
        )
        assert texture.resource_id == "12345"
        assert texture.name == "test_texture"
        assert texture.width == 1024
        assert texture.height == 1024
        assert texture.depth == 1
        assert texture.format == "RGBA8"
        assert texture.mips == 1
        assert texture.array_size == 1


class TestPassInfo:
    """Tests for PassInfo dataclass."""

    def test_creation_empty(self):
        """Test creating empty PassInfo."""
        pass_info = PassInfo(
            name="TestPass",
            draw_calls=[],
            duration_ms=0.0
        )
        assert pass_info.name == "TestPass"
        assert pass_info.draw_count == 0
        assert pass_info.duration_ms == 0.0

    def test_creation_with_draws(self):
        """Test creating PassInfo with draw calls."""
        draws = [
            DrawCallInfo(1, 100, "Draw1", 0.5),
            DrawCallInfo(2, 101, "Draw2", 0.3)
        ]
        pass_info = PassInfo(
            name="TestPass",
            draw_calls=draws,
            duration_ms=0.8
        )
        assert pass_info.draw_count == 2
        assert pass_info.duration_ms == 0.8


class TestRDCAnalysisData:
    """Tests for RDCAnalysisData dataclass."""

    def test_creation(self):
        """Test creating RDCAnalysisData."""
        summary = RDCSummary("Vulkan", 100, 10, 1)
        draws = [DrawCallInfo(1, 100, "Draw1", 0.5)]
        shaders = {"shader1": ShaderInfo("shader1", "Pixel")}
        textures = [TextureInfo("1", "tex1", 512, 512, 1)]
        passes = [PassInfo("Pass1", draws, 0.5)]

        data = RDCAnalysisData(
            summary=summary,
            draws=draws,
            shaders=shaders,
            textures=textures,
            passes=passes
        )
        assert data.summary.api_type == "Vulkan"
        assert len(data.draws) == 1
        assert len(data.shaders) == 1
        assert len(data.textures) == 1
        assert len(data.passes) == 1


class TestAnalyzeRDCFile:
    """Tests for analyze_rdc_file convenience function."""

    def test_file_not_found(self):
        """Test that FileNotFoundError is raised for non-existent file."""
        with patch('rd_mcp.rdc_analyzer._RENDERDOC_AVAILABLE', True):
            with pytest.raises(FileNotFoundError):
                analyze_rdc_file("/nonexistent/path/to/file.rdc")

    @patch('rd_mcp.rdc_analyzer.RDCAnalyzer')
    def test_successful_analysis(self, mock_analyzer_class):
        """Test successful analysis through convenience function."""
        # Setup mock
        mock_analyzer = MagicMock()
        mock_data = MagicMock()
        mock_data.summary.api_type = "Vulkan"
        mock_analyzer.analyze_file.return_value = mock_data
        mock_analyzer_class.return_value = mock_analyzer

        with patch('rd_mcp.rdc_analyzer._RENDERDOC_AVAILABLE', True):
            with patch('pathlib.Path.exists', return_value=True):
                result = analyze_rdc_file("test.rdc")

                # Verify
                mock_analyzer.analyze_file.assert_called_once()
                assert result == mock_data
