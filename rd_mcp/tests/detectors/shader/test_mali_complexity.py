# rd_mcp/tests/detectors/shader/test_mali_complexity.py
"""Tests for the Mali complexity detector module."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any

from rd_mcp.detectors.shader.mali_complexity import (
    MaliComplexityDetector,
    MaliShaderMetrics,
    MaliAnalysisResult,
)
from rd_mcp.detectors.shader.malioc_runner import MaliocOutput
from rd_mcp.models import IssueSeverity


class TestMaliShaderMetrics:
    """Tests for MaliShaderMetrics dataclass."""
    
    def test_creation_minimal(self):
        """Test minimal metrics creation."""
        metrics = MaliShaderMetrics(
            shader_name="test_shader",
            stage="Fragment"
        )
        assert metrics.shader_name == "test_shader"
        assert metrics.stage == "Fragment"
        assert metrics.total_cycles == 0.0
        assert metrics.work_registers == 0
        assert metrics.arithmetic_cycles == 0.0
    
    def test_creation_full(self):
        """Test full metrics creation."""
        metrics = MaliShaderMetrics(
            shader_name="complex_shader",
            stage="Fragment",
            total_cycles=250.0,
            work_registers=48,
            uniform_registers=24,
            arithmetic_cycles=100.0,
            load_store_cycles=50.0,
            texture_cycles=60.0,
            varying_cycles=40.0,
            longest_path_cycles=250.0,
            shortest_path_cycles=100.0
        )
        assert metrics.total_cycles == 250.0
        assert metrics.work_registers == 48
        assert metrics.uniform_registers == 24
        assert metrics.arithmetic_cycles == 100.0
    
    def test_is_complex_property(self):
        """Test is_complex property."""
        # Not complex
        simple = MaliShaderMetrics(shader_name="simple", stage="Fragment", total_cycles=30)
        assert simple.is_complex is False
        
        # Complex by cycles
        complex_cycles = MaliShaderMetrics(shader_name="complex", stage="Fragment", total_cycles=100)
        assert complex_cycles.is_complex is True
        
        # Complex by registers
        complex_regs = MaliShaderMetrics(shader_name="complex", stage="Fragment", work_registers=40)
        assert complex_regs.is_complex is True


class TestMaliAnalysisResult:
    """Tests for MaliAnalysisResult dataclass."""
    
    def test_creation(self):
        """Test result creation."""
        metrics = MaliShaderMetrics(
            shader_name="test",
            stage="Fragment",
            total_cycles=100.0,
            work_registers=16
        )
        result = MaliAnalysisResult(
            shaders=[metrics],
            malioc_available=True
        )
        assert result.total_shaders_analyzed == 1
        assert result.malioc_available is True
    
    def test_complex_shaders_property(self):
        """Test complex_shaders property."""
        simple = MaliShaderMetrics(shader_name="simple", stage="Fragment", total_cycles=30)
        complex_shader = MaliShaderMetrics(shader_name="complex", stage="Fragment", total_cycles=100)
        
        result = MaliAnalysisResult(shaders=[simple, complex_shader])
        assert len(result.complex_shaders) == 1
        assert result.complex_shaders[0].shader_name == "complex"


class TestMaliComplexityDetector:
    """Tests for MaliComplexityDetector class."""
    
    def test_init_default_thresholds(self):
        """Test initialization with default thresholds."""
        detector = MaliComplexityDetector({})
        assert detector._mali_thresholds["mali_max_cycles"] == 50
        assert detector._mali_thresholds["mali_max_registers"] == 32
        # mali_enabled defaults to False to avoid noisy suggestions
        assert detector._mali_thresholds["mali_enabled"] is False
    
    def test_init_custom_thresholds(self):
        """Test initialization with custom thresholds."""
        config = {
            "mali_max_cycles": 100,
            "mali_max_registers": 48,
            "mali_enabled": False
        }
        detector = MaliComplexityDetector(config)
        assert detector._mali_thresholds["mali_max_cycles"] == 100
        assert detector._mali_thresholds["mali_max_registers"] == 48
        assert detector._mali_thresholds["mali_enabled"] is False
    
    def test_is_enabled_property(self):
        """Test is_enabled property."""
        detector_enabled = MaliComplexityDetector({"mali_enabled": True})
        assert detector_enabled.is_enabled is True
        
        detector_disabled = MaliComplexityDetector({"mali_enabled": False})
        assert detector_disabled.is_enabled is False
    
    def test_detect_no_shaders(self):
        """Test detection with empty shader dict when malioc unavailable."""
        # Explicitly enable Mali detection to test malioc unavailable message
        detector = MaliComplexityDetector({"mali_enabled": True})
        issues = detector.detect({})
        # When malioc is unavailable, returns suggestion even for empty shaders
        # This helps users understand why no Mali analysis is performed
        assert len(issues) == 1
        assert issues[0].type == "mali_malioc_not_found"
    
    @patch.object(MaliComplexityDetector, "_check_malioc_available", return_value=False)
    def test_detect_malioc_unavailable(self, mock_check):
        """Test detection when malioc is unavailable returns a suggestion."""
        # Explicitly enable Mali to test the malioc not found message
        detector = MaliComplexityDetector({"mali_enabled": True})
        shaders = {
            "test_shader": {
                "source": "void main() {}",
                "stage": "Fragment"
            }
        }
        issues = detector.detect(shaders)
        # Now returns a helpful suggestion about malioc installation
        assert len(issues) == 1
        assert issues[0].type == "mali_malioc_not_found"
        assert issues[0].severity == IssueSeverity.SUGGESTION
        assert "malioc" in issues[0].description.lower() or "Mali" in issues[0].description
    
    def test_detect_with_mali_analysis_result(self):
        """Test detection with MaliAnalysisResult input."""
        # Create result with high cycle shader
        metrics = MaliShaderMetrics(
            shader_name="expensive",
            stage="Fragment",
            total_cycles=100.0,  # Over default threshold of 50
            work_registers=16
        )
        result = MaliAnalysisResult(
            shaders=[metrics],
            malioc_available=True
        )
        
        # Enable Mali detection for testing
        detector = MaliComplexityDetector({"mali_enabled": True})
        issues = detector.detect(result)
        
        assert len(issues) >= 1
        cycle_issue = [i for i in issues if "周期" in i.description]
        assert len(cycle_issue) >= 1
    
    def test_detect_high_register_usage(self):
        """Test detection of shader exceeding register threshold."""
        metrics = MaliShaderMetrics(
            shader_name="register_heavy",
            stage="Fragment",
            total_cycles=30.0,  # Under cycle threshold
            work_registers=48  # Over default register threshold of 32
        )
        result = MaliAnalysisResult(
            shaders=[metrics],
            malioc_available=True
        )
        
        # Enable Mali detection for testing
        detector = MaliComplexityDetector({"mali_enabled": True})
        issues = detector.detect(result)
        
        assert len(issues) >= 1
        register_issue = [i for i in issues if "寄存器" in i.description]
        assert len(register_issue) >= 1
    
    def test_detect_shader_under_thresholds(self):
        """Test detection of shader that passes all checks."""
        metrics = MaliShaderMetrics(
            shader_name="efficient",
            stage="Fragment",
            total_cycles=30.0,  # Under threshold
            work_registers=16  # Under threshold
        )
        result = MaliAnalysisResult(
            shaders=[metrics],
            malioc_available=True
        )
        
        # Enable Mali detection for testing
        detector = MaliComplexityDetector({"mali_enabled": True})
        issues = detector.detect(result)
        assert len(issues) == 0
    
    def test_detect_many_complex_shaders_warning(self):
        """Test warning when many complex shaders detected."""
        # Create 5 complex shaders (threshold is 3)
        shaders_list = []
        for i in range(5):
            shaders_list.append(MaliShaderMetrics(
                shader_name=f"complex_{i}",
                stage="Fragment",
                total_cycles=100.0  # Over threshold
            ))
        
        result = MaliAnalysisResult(
            shaders=shaders_list,
            malioc_available=True
        )
        
        # Enable Mali detection for testing
        detector = MaliComplexityDetector({"mali_enabled": True})
        issues = detector.detect(result)
        
        # Should have individual issues plus summary issue
        summary_issues = [i for i in issues if "mali_many_complex_shaders" in i.type]
        assert len(summary_issues) == 1


class TestMaliComplexityDetectorEdgeCases:
    """Edge case tests for MaliComplexityDetector."""
    
    def test_detect_stack_spilling(self):
        """Test detection of stack spilling."""
        metrics = MaliShaderMetrics(
            shader_name="spilling_shader",
            stage="Fragment",
            total_cycles=30.0,
            work_registers=16,
            stack_spilling=True
        )
        result = MaliAnalysisResult(
            shaders=[metrics],
            malioc_available=True
        )
        
        # Enable Mali detection for testing
        detector = MaliComplexityDetector({"mali_enabled": True})
        issues = detector.detect(result)
        
        spilling_issues = [i for i in issues if "mali_stack_spilling" in i.type]
        assert len(spilling_issues) == 1
    
    def test_detect_excessive_texture_samples(self):
        """Test detection of excessive texture samples."""
        metrics = MaliShaderMetrics(
            shader_name="texture_heavy",
            stage="Fragment",
            total_cycles=30.0,
            texture_samples=15  # Over default threshold of 8
        )
        result = MaliAnalysisResult(
            shaders=[metrics],
            malioc_available=True
        )
        
        # Enable Mali detection for testing
        detector = MaliComplexityDetector({"mali_enabled": True})
        issues = detector.detect(result)
        
        texture_issues = [i for i in issues if "mali_excessive_texture_samples" in i.type]
        assert len(texture_issues) == 1
    
    def test_detect_analysis_errors_reported(self):
        """Test that analysis errors are reported as suggestions."""
        result = MaliAnalysisResult(
            shaders=[],
            malioc_available=True,
            errors=["Failed to compile shader X"]
        )
        
        # Enable Mali detection for testing
        detector = MaliComplexityDetector({"mali_enabled": True})
        issues = detector.detect(result)
        
        warning_issues = [i for i in issues if "mali_analysis_warning" in i.type]
        assert len(warning_issues) == 1
    
    def test_disabled_detector(self):
        """Test that disabled detector returns no issues."""
        detector = MaliComplexityDetector({"mali_enabled": False})
        shaders = {
            "test": {
                "source": "void main() {}",
                "stage": "Fragment"
            }
        }
        # When disabled, detect should return empty list immediately
        issues = detector.detect(shaders)
        assert len(issues) == 0
