# rd_mcp/detectors/resource.py
from rd_mcp.models import Issue, IssueSeverity
from typing import List, Dict, Any

class ResourceDetector:
    def __init__(self, threshold: Dict):
        self.large_texture_size = threshold.get("large_texture_size", 4096)

    def detect_large_textures(self, resources: List[Dict[str, Any]]) -> List[Issue]:
        issues = []
        for resource in resources:
            width = resource.get("width", 0)
            height = resource.get("height", 0)
            if width > self.large_texture_size or height > self.large_texture_size:
                issues.append(Issue(
                    type="large_texture",
                    severity=IssueSeverity.WARNING,
                    description=f"纹理 {resource.get('name', 'unknown')} 尺寸过大 ({width}x{height})，考虑使用 mipmap 或降低分辨率",
                    location=f"Resource: {resource.get('name', 'unknown')}",
                    impact="medium"
                ))
        return issues
