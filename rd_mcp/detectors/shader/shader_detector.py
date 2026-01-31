# rd_mcp/detectors/shader/shader_detector.py
"""Shader instruction count detector.

This module provides detection of shaders with excessive instruction counts.
"""
from rd_mcp.models import Issue, IssueSeverity
from typing import List, Dict, Any


class ShaderDetector:
    """Detector for expensive shaders based on instruction count."""
    
    def __init__(self, threshold: Dict):
        """Initialize the shader detector.
        
        Args:
            threshold: Dictionary containing threshold configuration.
                      Expected key: 'expensive_shader_instructions'
        """
        self.expensive_threshold = threshold.get("expensive_shader_instructions", 500)

    def detect_expensive_shaders(self, shaders: Dict[str, Dict[str, Any]]) -> List[Issue]:
        """Detect shaders with excessive instruction counts.
        
        Args:
            shaders: Dictionary mapping shader names to shader data.
                    Each shader data should have an 'instructions' key.
        
        Returns:
            List of Issue objects for shaders exceeding the threshold.
        """
        issues = []
        for shader_name, shader_data in shaders.items():
            instructions = shader_data.get("instructions", 0)
            if instructions > self.expensive_threshold:
                issues.append(Issue(
                    type="expensive_shader",
                    severity=IssueSeverity.WARNING,
                    description=f"着色器 {shader_name} 指令数过高 ({instructions})，超过阈值 {self.expensive_threshold}",
                    location=f"Shader: {shader_name}",
                    impact="medium"
                ))
        return issues
