import re
from typing import List, Dict
from rd_mcp.detectors.base import BaseDetector
from rd_mcp.models import Issue, IssueSeverity, ModelStats
from rd_mcp.rdc_analyzer_cmd import DrawCallInfo

class ModelStatsDetector(BaseDetector):
    """Detector for model-level statistics and heavy models."""

    @property
    def name(self) -> str:
        return "model_stats"

    def detect(self, draws: List[DrawCallInfo]) -> List[Issue]:
        """Detect heavy models.

        Args:
            draws: List of draw calls from frame

        Returns:
            List of issues found
        """
        max_per_model = self.thresholds.get("max_triangles_per_model", 50000)
        model_stats = self.extract_model_stats(draws)

        issues = []
        for name, stats in model_stats.items():
            if stats.triangle_count > max_per_model:
                issues.append(Issue(
                    type="heavy_model",
                    severity=IssueSeverity.WARNING,
                    description=(
                        f"模型 '{name}' 三角形 {stats.triangle_count:,}，"
                        f"超过阈值 {max_per_model:,}"
                    ),
                    location=f"Model: {name} ({stats.draw_calls} Draw Calls)",
                    impact="medium"
                ))

        return issues

    def extract_model_stats(self, draws: List[DrawCallInfo]) -> Dict[str, ModelStats]:
        """Extract statistics grouped by inferred model name.

        Args:
            draws: List of draw calls

        Returns:
            Dictionary mapping model names to ModelStats
        """
        models: Dict[str, ModelStats] = {}

        for draw in draws:
            model_name = self._infer_model_name(draw)

            if model_name not in models:
                models[model_name] = ModelStats(name=model_name)

            stats = models[model_name]
            stats.draw_calls += 1
            stats.triangle_count += draw.vertex_count // 3
            stats.vertex_count += draw.vertex_count

            if draw.marker and draw.marker not in stats.passes:
                stats.passes.append(draw.marker)

        return models

    def _infer_model_name(self, draw: DrawCallInfo) -> str:
        """Intelligently infer model name from draw call.

        Priority:
        1. Marker/label
        2. Parse from draw name patterns
        3. Default to "Unknown"

        Args:
            draw: Draw call info

        Returns:
            Inferred model name
        """
        # Rule 1: Use marker
        if draw.marker:
            return draw.marker

        # Rule 2: Parse from name patterns
        # Pattern: "Model_XXX", "Draw_XXX", etc.
        patterns = [
            r"Model[_\s]+([A-Za-z]+)",  # Match letters only, stop at underscore/number
            r"Draw[_\s]+([A-Za-z]+)",
            r"Mesh[_\s]+([A-Za-z]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, draw.name, re.IGNORECASE)
            if match:
                return match.group(1)

        return "Unknown"
