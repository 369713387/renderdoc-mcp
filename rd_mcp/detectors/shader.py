# rd_mcp/detectors/shader.py
from rd_mcp.models import Issue, IssueSeverity
from typing import List, Dict, Any

class ShaderDetector:
    def __init__(self, threshold: Dict):
        self.expensive_threshold = threshold.get("expensive_shader_instructions", 500)

    def detect_expensive_shaders(self, shaders: Dict[str, Dict[str, Any]]) -> List[Issue]:
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
