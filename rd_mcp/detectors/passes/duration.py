from typing import List
from rd_mcp.detectors.base import BaseDetector
from rd_mcp.models import Issue, IssueSeverity
from rd_mcp.rdc_analyzer_cmd import PassInfo

class PassDurationDetector(BaseDetector):
    """Detector for slow render passes."""

    @property
    def name(self) -> str:
        return "pass_duration"

    def detect(self, passes: List[PassInfo]) -> List[Issue]:
        """Detect passes exceeding duration threshold.

        Args:
            passes: List of render passes

        Returns:
            List of slow pass issues
        """
        max_duration = self.thresholds.get("max_duration_ms", 1.0)
        issues = []

        for pass_info in passes:
            if pass_info.duration_ms > max_duration:
                resolution_str = f" ({pass_info.resolution})" if pass_info.resolution else ""
                issues.append(Issue(
                    type="slow_pass",
                    severity=IssueSeverity.CRITICAL,
                    description=(
                        f"Pass '{pass_info.name}' 耗时 {pass_info.duration_ms:.2f}ms，"
                        f"超过阈值 {max_duration:.2f}ms"
                    ),
                    location=f"Pass: {pass_info.name}{resolution_str}",
                    impact="high"
                ))

        return issues
