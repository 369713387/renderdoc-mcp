# rd_mcp/detectors/drawcall.py
from rd_mcp.models import Issue, IssueSeverity
from typing import List, Dict

class DrawCallDetector:
    def __init__(self, threshold: Dict):
        self.max_draw_calls = threshold.get("max_draw_calls", 1000)

    def detect_excessive_draw_calls(self, draw_call_count: int) -> List[Issue]:
        if draw_call_count > self.max_draw_calls:
            return [
                Issue(
                    type="excessive_draw_calls",
                    severity=IssueSeverity.CRITICAL,
                    description=f"Draw call 数量过多 ({draw_call_count})，超过阈值 {self.max_draw_calls}，建议合并",
                    location="Frame",
                    impact="high"
                )
            ]
        return []
