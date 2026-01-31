# rd_mcp/detectors/shader/__init__.py
"""Shader-related performance detectors.

This module contains detectors for analyzing shader complexity and performance,
including Mali GPU-specific analysis using malioc.
"""

from rd_mcp.detectors.shader.shader_detector import ShaderDetector
from rd_mcp.detectors.shader.mali_complexity import (
    MaliComplexityDetector,
    MaliShaderMetrics,
    MaliAnalysisResult,
)
from rd_mcp.detectors.shader.malioc_runner import (
    MaliocRunner,
    MaliocOutput,
)
from rd_mcp.detectors.shader.shader_extractor import (
    ShaderExtractor,
    ExtractedShader,
)

__all__ = [
    "ShaderDetector",
    "MaliComplexityDetector",
    "MaliShaderMetrics",
    "MaliAnalysisResult",
    "MaliocRunner",
    "MaliocOutput",
    "ShaderExtractor",
    "ExtractedShader",
]
