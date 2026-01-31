"""Tests for MCP server functionality."""
import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import json

from rd_mcp.server import analyze_rdc
from rd_mcp.analyzer import Analyzer
from rd_mcp.models import ReportSummary, AnalysisResult
from rd_mcp.rdc_analyzer_cmd import RDCAnalysisData, RDCSummary, DrawCallInfo, ShaderInfo, TextureInfo, PassInfo


def _create_mock_result(api_type="Vulkan", total_draw_calls=1000, total_shaders=10):
    """Helper to create mock AnalysisResult."""
    mock_result = Mock()
    mock_result.summary = Mock()
    mock_result.summary.api_type = api_type
    mock_result.summary.total_draw_calls = total_draw_calls
    mock_result.summary.total_shaders = total_shaders
    mock_result.summary.frame_count = 1
    mock_result.issues = {"critical": [], "warnings": [], "suggestions": []}
    mock_result.metrics = {"total_issues": 0}
    mock_result.model_stats = {}
    mock_result.pass_switches = None
    mock_result.errors = []
    return mock_result


class TestAnalyzeRDC:
    """Test cases for the analyze_rdc function."""

    @pytest.mark.asyncio
    @patch('rd_mcp.server.analyze_rdc_file')
    @patch('rd_mcp.server.Analyzer')
    async def test_analyze_rdc_without_preset(self, mock_analyzer_class, mock_analyze_rdc_file):
        """Test analyze_rdc without preset parameter (backward compatibility)."""
        # Mock the RDC data
        mock_rdc_data = Mock(spec=RDCAnalysisData)
        mock_rdc_data.summary = Mock(spec=RDCSummary)
        mock_rdc_data.summary.api_type = "Vulkan"
        mock_rdc_data.summary.total_draw_calls = 1000
        mock_rdc_data.summary.total_shaders = 10
        mock_rdc_data.summary.frame_count = 1

        # Mock shader with proper attribute access
        mock_shader = Mock()
        mock_shader.instruction_count = 100
        mock_shader.stage = "PS"
        mock_shader.binding_count = 5
        mock_rdc_data.shaders = {"shader1": mock_shader}

        # Mock texture with proper attribute access
        mock_texture = Mock()
        mock_texture.name = "tex1"
        mock_texture.width = 1024
        mock_texture.height = 1024
        mock_texture.depth = 1
        mock_texture.format = "RGBA8"
        mock_rdc_data.textures = [mock_texture]

        # Mock pass with proper attribute access
        mock_pass = Mock()
        mock_pass.name = "pass1"
        mock_pass.duration_ms = 1.5
        mock_pass.resolution = "1920x1080"
        mock_pass.draw_count = 5
        mock_rdc_data.passes = [mock_pass]
        mock_rdc_data.draws = None  # No draws attribute

        mock_analyze_rdc_file.return_value = mock_rdc_data

        # Mock analyzer
        mock_analyzer = Mock()
        mock_analyzer.analyze.return_value = _create_mock_result()
        mock_analyzer_class.return_value = mock_analyzer

        # Test function
        arguments = {
            "rdc_path": "test.rdc",
            "config_path": None
        }

        result = await analyze_rdc(arguments)

        # Verify calls
        mock_analyze_rdc_file.assert_called_once_with("test.rdc")
        mock_analyzer_class.assert_called_once_with(config_path=None)

        # Check that analyze was called
        mock_analyzer.analyze.assert_called_once()

        # Verify result
        assert len(result) == 1
        assert result[0].type == "text"
        assert "# RenderDoc RDC Analysis Report" in result[0].text

    @pytest.mark.asyncio
    @patch('rd_mcp.server.analyze_rdc_file')
    @patch('rd_mcp.server.Analyzer')
    async def test_analyze_rdc_with_preset(self, mock_analyzer_class, mock_analyze_rdc_file):
        """Test analyze_rdc with preset parameter."""
        # Mock the RDC data
        mock_rdc_data = Mock(spec=RDCAnalysisData)
        mock_rdc_data.summary = Mock(spec=RDCSummary)
        mock_rdc_data.summary.api_type = "Vulkan"
        mock_rdc_data.summary.total_draw_calls = 1000
        mock_rdc_data.summary.total_shaders = 10
        mock_rdc_data.summary.frame_count = 1
        mock_rdc_data.shaders = {}
        mock_rdc_data.textures = []
        mock_rdc_data.passes = []

        mock_draw = Mock()
        mock_draw.draw_id = 1
        mock_draw.name = "draw1"
        mock_draw.gpu_duration_ms = 1.0
        mock_draw.vertex_count = 100
        mock_draw.marker = ""
        mock_rdc_data.draws = [mock_draw]

        mock_analyze_rdc_file.return_value = mock_rdc_data

        # Mock analyzer
        mock_analyzer = Mock()
        mock_analyzer.analyze.return_value = _create_mock_result()
        mock_analyzer_class.return_value = mock_analyzer

        # Test function with preset
        arguments = {
            "rdc_path": "test.rdc",
            "preset": "mobile-balanced"
        }

        result = await analyze_rdc(arguments)

        # Verify that preset was passed to Analyzer constructor
        mock_analyzer_class.assert_called_once_with(preset="mobile-balanced")
        mock_analyzer.analyze.assert_called_once()

        # Check that draws were passed to analyze
        # Note: analyzer.analyze expects (summary, shaders, resources, draws, passes)
        args, kwargs = mock_analyzer.analyze.call_args
        assert args[3] is not None  # draws should be passed (4th argument, index 3)
        assert len(args[3]) == 1  # one draw call

    @pytest.mark.asyncio
    @patch('rd_mcp.server.analyze_rdc_file')
    @patch('rd_mcp.server.Analyzer')
    async def test_analyze_rdc_with_both_preset_and_config(self, mock_analyzer_class, mock_analyze_rdc_file):
        """Test analyze_rdc with both preset and config_path (preset should take precedence)."""
        # Mock the RDC data
        mock_rdc_data = Mock(spec=RDCAnalysisData)
        mock_rdc_data.summary = Mock(spec=RDCSummary)
        mock_rdc_data.summary.api_type = "Vulkan"
        mock_rdc_data.summary.total_draw_calls = 500
        mock_rdc_data.summary.total_shaders = 5
        mock_rdc_data.summary.frame_count = 1
        mock_rdc_data.shaders = {}
        mock_rdc_data.textures = []
        mock_rdc_data.passes = []
        mock_rdc_data.draws = []

        mock_analyze_rdc_file.return_value = mock_rdc_data

        # Mock analyzer
        mock_analyzer = Mock()
        mock_analyzer.analyze.return_value = _create_mock_result(total_draw_calls=500, total_shaders=5)
        mock_analyzer_class.return_value = mock_analyzer

        # Test function with both preset and config
        arguments = {
            "rdc_path": "test.rdc",
            "config_path": "custom_config.json",
            "preset": "mobile-aggressive"
        }

        result = await analyze_rdc(arguments)

        # Verify that preset takes precedence (Analyzer should be called with preset)
        mock_analyzer_class.assert_called_once_with(preset="mobile-aggressive")

    @pytest.mark.asyncio
    @patch('rd_mcp.server.analyze_rdc_file')
    async def test_analyze_rdc_file_not_found(self, mock_analyze_rdc_file):
        """Test analyze_rdc when RDC file is not found."""
        mock_analyze_rdc_file.side_effect = FileNotFoundError("RDC file not found")

        arguments = {
            "rdc_path": "nonexistent.rdc"
        }

        result = await analyze_rdc(arguments)

        assert len(result) == 1
        assert result[0].type == "text"
        assert "Error: RDC file not found" in result[0].text

    @pytest.mark.asyncio
    @patch('rd_mcp.server.analyze_rdc_file')
    async def test_analyze_rdc_runtime_error(self, mock_analyze_rdc_file):
        """Test analyze_rdc when runtime error occurs."""
        mock_analyze_rdc_file.side_effect = RuntimeError("Analysis failed")

        arguments = {
            "rdc_path": "test.rdc"
        }

        result = await analyze_rdc(arguments)

        assert len(result) == 1
        assert result[0].type == "text"
        assert "Error: Analysis failed" in result[0].text

    @pytest.mark.asyncio
    @patch('rd_mcp.server.analyze_rdc_file')
    @patch('rd_mcp.server.Analyzer')
    async def test_analyze_rdc_with_draws_data(self, mock_analyzer_class, mock_analyze_rdc_file):
        """Test that draws data is properly extracted and passed to analyzer."""
        # Mock the RDC data with draws
        mock_draw = Mock()
        mock_draw.draw_id = 1
        mock_draw.event_id = 1
        mock_draw.name = "test_draw"
        mock_draw.gpu_duration_ms = 1.0
        mock_draw.vertex_count = 1000
        mock_draw.marker = "test_pass"

        mock_rdc_data = Mock(spec=RDCAnalysisData)
        mock_rdc_data.summary = Mock(spec=RDCSummary)
        mock_rdc_data.summary.api_type = "OpenGL"
        mock_rdc_data.summary.total_draw_calls = 1
        mock_rdc_data.summary.total_shaders = 0
        mock_rdc_data.summary.frame_count = 1
        mock_rdc_data.shaders = {}
        mock_rdc_data.textures = []
        mock_rdc_data.passes = []
        mock_rdc_data.draws = [mock_draw]

        mock_analyze_rdc_file.return_value = mock_rdc_data

        # Mock analyzer
        mock_analyzer = Mock()
        mock_analyzer.analyze.return_value = _create_mock_result(
            api_type="OpenGL",
            total_draw_calls=1,
            total_shaders=0
        )
        mock_analyzer_class.return_value = mock_analyzer

        # Test function
        arguments = {
            "rdc_path": "test.rdc",
            "config_path": None
        }

        result = await analyze_rdc(arguments)

        # Verify that draws were extracted and passed
        # Note: analyzer.analyze expects (summary, shaders, resources, draws, passes)
        mock_analyzer.analyze.assert_called_once()
        args, kwargs = mock_analyzer.analyze.call_args
        assert args[3] is not None  # draws should be passed (4th argument, index 3)
        assert len(args[3]) == 1  # one draw call

    @pytest.mark.asyncio
    async def test_analyze_rdc_missing_rdc_path(self):
        """Test analyze_rdc when rdc_path is missing."""
        arguments = {
            "config_path": "config.json"
        }

        result = await analyze_rdc(arguments)

        assert len(result) == 1
        assert result[0].type == "text"
        assert "Error: rdc_path is required" in result[0].text