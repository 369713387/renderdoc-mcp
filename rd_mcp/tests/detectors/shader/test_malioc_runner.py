# rd_mcp/tests/detectors/shader/test_malioc_runner.py
"""Tests for the malioc runner module."""
import pytest
from unittest.mock import Mock, patch, MagicMock
import json
import subprocess
from pathlib import Path

from rd_mcp.detectors.shader.malioc_runner import MaliocRunner, MaliocOutput


class TestMaliocRunner:
    """Tests for MaliocRunner class."""
    
    def test_init_default_settings(self):
        """Test default initialization."""
        runner = MaliocRunner()
        assert runner._malioc_path is None
        assert runner._cached_path is None
        assert runner._version is None
    
    def test_init_custom_path(self):
        """Test initialization with custom path."""
        runner = MaliocRunner(malioc_path="/custom/malioc")
        assert runner._malioc_path == "/custom/malioc"
    
    @patch.object(MaliocRunner, "_find_malioc")
    def test_is_available_when_found(self, mock_find):
        """Test availability check when malioc is found."""
        mock_find.return_value = "/usr/bin/malioc"
        runner = MaliocRunner()
        
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="malioc v7.5.0")
            assert runner.is_available() is True
    
    @patch.object(MaliocRunner, "_find_malioc")
    def test_is_available_when_not_found(self, mock_find):
        """Test availability check when malioc is not found."""
        mock_find.return_value = None
        runner = MaliocRunner()
        assert runner.is_available() is False


class TestMaliocOutput:
    """Tests for MaliocOutput dataclass."""
    
    def test_creation_minimal(self):
        """Test minimal MaliocOutput creation."""
        output = MaliocOutput(
            success=True,
            total_cycles=100.0,
            longest_path_cycles=100.0,
            shortest_path_cycles=50.0
        )
        assert output.success is True
        assert output.total_cycles == 100.0
        assert output.longest_path_cycles == 100.0
        assert output.shortest_path_cycles == 50.0
        assert output.work_registers == 0  # Default
        assert output.uniform_registers == 0  # Default
    
    def test_creation_full(self):
        """Test full MaliocOutput creation."""
        output = MaliocOutput(
            success=True,
            target_gpu="Mali-G78",
            work_registers=32,
            uniform_registers=16,
            total_cycles=150.0,
            longest_path_cycles=150.0,
            shortest_path_cycles=75.0,
            arithmetic_cycles=50.0,
            load_store_cycles=40.0,
            texture_cycles=30.0,
            varying_cycles=20.0
        )
        assert output.total_cycles == 150.0
        assert output.work_registers == 32
        assert output.uniform_registers == 16
        assert output.arithmetic_cycles == 50.0
        assert output.load_store_cycles == 40.0
        assert output.texture_cycles == 30.0
        assert output.varying_cycles == 20.0
        assert output.target_gpu == "Mali-G78"
    
    def test_default_values(self):
        """Test default values for MaliocOutput."""
        output = MaliocOutput()
        assert output.success is False
        assert output.error_message == ""
        assert output.target_gpu == ""
        assert output.work_registers == 0
        assert output.total_cycles == 0.0
        assert output.stack_spilling is False


class TestMaliocRunnerAnalyze:
    """Tests for MaliocRunner.analyze_shader method."""
    
    @patch.object(MaliocRunner, "is_available", return_value=False)
    def test_analyze_shader_not_available(self, mock_available):
        """Test analysis when malioc is not available."""
        runner = MaliocRunner()
        result = runner.analyze_shader(
            source="void main() {}",
            stage="Vertex",
            shader_name="test"
        )
        # Should return None or empty metrics when not available
        assert result is None or not result.success


class TestMaliocRunnerEdgeCases:
    """Edge case tests for MaliocRunner."""
    
    def test_runner_with_invalid_path(self):
        """Test runner initialization with invalid path."""
        runner = MaliocRunner(malioc_path="/invalid/path/malioc")
        assert runner.is_available() is False
    
    @patch.object(MaliocRunner, "_find_malioc")
    def test_version_extraction(self, mock_find):
        """Test version extraction when available."""
        mock_find.return_value = "/usr/bin/malioc"
        runner = MaliocRunner()
        
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="Mali Offline Compiler v7.5.0"
            )
            version = runner.get_version()
            assert version is not None or version == ""  # May vary by implementation
