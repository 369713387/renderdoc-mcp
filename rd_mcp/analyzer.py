# rd_mcp/analyzer.py
from rd_mcp.config import Config
from rd_mcp.detectors.drawcall import DrawCallDetector
from rd_mcp.detectors.shader import ShaderDetector
from rd_mcp.detectors.resource import ResourceDetector
from rd_mcp.models import ReportSummary, AnalysisResult
from typing import Dict, List, Any


class Analyzer:
    """Main analyzer for RenderDoc reports.

    This class orchestrates the analysis of RenderDoc reports by coordinating
    multiple detectors to identify performance issues and provide insights.
    """

    def __init__(self, config_path=None):
        """Initialize the analyzer with configuration.

        Args:
            config_path: Optional path to custom configuration file.
                        If None, uses default configuration.
        """
        from pathlib import Path
        path = Path(config_path) if config_path else None
        self.config = Config.load(path)
        # Convert thresholds to legacy flat dict for backward compatibility with detectors
        thresholds_dict = self.config.thresholds.to_legacy_dict()
        self.drawcall_detector = DrawCallDetector(thresholds_dict)
        self.shader_detector = ShaderDetector(thresholds_dict)
        self.resource_detector = ResourceDetector(thresholds_dict)

    def analyze(
        self,
        summary: ReportSummary,
        shaders: Dict[str, Dict[str, Any]],
        resources: List[Dict[str, Any]]
    ) -> AnalysisResult:
        """Analyze a RenderDoc report and identify performance issues.

        Args:
            summary: Report summary containing API type, draw calls, etc.
            shaders: Dictionary of shader data with instruction counts
            resources: List of resource data including texture dimensions

        Returns:
            AnalysisResult containing summary, issues grouped by severity,
            and analysis metrics
        """
        issues = {
            "critical": [],
            "warnings": [],
            "suggestions": []
        }

        # Map severity enum to plural form for dictionary keys
        severity_map = {
            "critical": "critical",
            "warning": "warnings",
            "suggestion": "suggestions"
        }

        # Detect excessive draw calls
        issues["critical"].extend(
            self.drawcall_detector.detect_excessive_draw_calls(summary.total_draw_calls)
        )

        # Detect expensive shaders
        for issue in self.shader_detector.detect_expensive_shaders(shaders):
            key = severity_map.get(issue.severity.value, issue.severity.value)
            issues[key].append(issue)

        # Detect large textures
        for issue in self.resource_detector.detect_large_textures(resources):
            key = severity_map.get(issue.severity.value, issue.severity.value)
            issues[key].append(issue)

        # Build metrics
        metrics = self._build_metrics(summary, issues)

        return AnalysisResult(
            summary=summary,
            issues=issues,
            metrics=metrics
        )

    def _build_metrics(
        self,
        summary: ReportSummary,
        issues: Dict[str, List]
    ) -> Dict[str, Any]:
        """Build analysis metrics from summary and issues.

        Args:
            summary: Report summary information
            issues: Issues grouped by severity

        Returns:
            Dictionary containing analysis metrics
        """
        critical_count = len(issues["critical"])
        warning_count = len(issues["warnings"])
        suggestion_count = len(issues["suggestions"])

        return {
            "total_issues": critical_count + warning_count + suggestion_count,
            "critical_count": critical_count,
            "warning_count": warning_count,
            "suggestion_count": suggestion_count,
            "api_type": summary.api_type,
            "draw_calls": summary.total_draw_calls,
            "shader_count": summary.total_shaders,
            "frame_count": summary.frame_count,
            "thresholds": {
                "max_draw_calls": self.config.thresholds.max_draw_calls,
                "expensive_shader_instructions": self.config.thresholds.expensive_shader_instructions,
                "large_texture_size": self.config.thresholds.large_texture_size
            }
        }
