from typing import List, Dict
from rd_mcp.detectors.base import BaseDetector
from rd_mcp.models import Issue, IssueSeverity
from rd_mcp.rdc_analyzer_cmd import DrawCallInfo

class TriangleCountDetector(BaseDetector):
    """Detector for excessive triangle count in frame."""

    @property
    def name(self) -> str:
        return "triangle_count"

    def detect(self, draws: List[DrawCallInfo]) -> List[Issue]:
        """Detect if total triangle count exceeds threshold.

        Args:
            draws: List of draw calls from frame

        Returns:
            List of issues found
        """
        max_triangles = self.thresholds.get("max_triangles", 100000)

        # Calculate total triangles
        total_triangles = sum(d.vertex_count // 3 for d in draws)

        if total_triangles > max_triangles:
            return [Issue(
                type="excessive_triangles",
                severity=IssueSeverity.CRITICAL,
                description=(
                    f"三角形数量过多 ({total_triangles:,})，超过阈值 {max_triangles:,}"
                ),
                location="Frame",
                impact="high"
            )]

        return []
