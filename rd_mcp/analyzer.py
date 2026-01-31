# rd_mcp/analyzer.py
from rd_mcp.config import Config
from rd_mcp.detectors.drawcall import DrawCallDetector
from rd_mcp.detectors.shader import ShaderDetector
from rd_mcp.detectors.resource import ResourceDetector
from rd_mcp.detectors.geometry.triangle_count import TriangleCountDetector
from rd_mcp.detectors.geometry.model_stats import ModelStatsDetector
from rd_mcp.detectors.passes.duration import PassDurationDetector
from rd_mcp.detectors.passes.switches import PassSwitchesDetector
from rd_mcp.detectors.shader.mali_complexity import MaliComplexityDetector
from rd_mcp.models import ReportSummary, AnalysisResult
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)


class Analyzer:
    """Main analyzer for RenderDoc reports.

    This class orchestrates the analysis of RenderDoc reports by coordinating
    multiple detectors to identify performance issues and provide insights.
    """

    def __init__(self, config_path=None, preset=None):
        """Initialize the analyzer with configuration.

        Args:
            config_path: Optional path to custom configuration file.
                        If None, uses default configuration.
            preset: Optional preset name to use (e.g., 'mobile-balanced').
                    Takes precedence over config_path if both provided.
        """
        from pathlib import Path

        # Load configuration
        if preset:
            self.config = Config.load_preset(preset)
        elif config_path:
            path = Path(config_path)
            self.config = Config.load(path)
        else:
            self.config = Config.load()

        # Convert thresholds to legacy flat dict for backward compatibility with detectors
        thresholds_dict = self.config.thresholds.to_legacy_dict()

        # Initialize original detectors
        self.drawcall_detector = DrawCallDetector(thresholds_dict)
        self.shader_detector = ShaderDetector(thresholds_dict)
        self.resource_detector = ResourceDetector(thresholds_dict)

        # Initialize new detectors
        self.triangle_count_detector = TriangleCountDetector(thresholds_dict)
        self.model_stats_detector = ModelStatsDetector(thresholds_dict)
        self.pass_duration_detector = PassDurationDetector(thresholds_dict)
        self.pass_switches_detector = PassSwitchesDetector(thresholds_dict)
        
        # Initialize Mali complexity detector (for mobile GPU analysis)
        self.mali_complexity_detector = MaliComplexityDetector(thresholds_dict)

    def analyze(
        self,
        summary: ReportSummary,
        shaders: Dict[str, Dict[str, Any]],
        resources: List[Dict[str, Any]],
        draws: Optional[List[Any]] = None,
        passes: Optional[List[Any]] = None
    ) -> AnalysisResult:
        """Analyze a RenderDoc report and identify performance issues.

        Args:
            summary: Report summary containing API type, draw calls, etc.
            shaders: Dictionary of shader data with instruction counts
            resources: List of resource data including texture dimensions
            draws: Optional list of draw calls for geometry/pass analysis
            passes: Optional list of render passes for duration analysis

        Returns:
            AnalysisResult containing summary, issues grouped by severity,
            and analysis metrics
        """
        issues = {
            "critical": [],
            "warnings": [],
            "suggestions": []
        }

        errors = []

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

        # Run new detectors if draws are provided
        model_stats = {}
        pass_switches = None

        if draws:
            try:
                # Detect excessive triangles
                for issue in self.triangle_count_detector.detect(draws):
                    key = severity_map.get(issue.severity.value, issue.severity.value)
                    issues[key].append(issue)

                # Detect heavy models and extract model stats
                for issue in self.model_stats_detector.detect(draws):
                    key = severity_map.get(issue.severity.value, issue.severity.value)
                    issues[key].append(issue)

                # Extract model statistics
                model_stats = self.model_stats_detector.extract_model_stats(draws)

                # Detect pass switches and extract switch info
                for issue in self.pass_switches_detector.detect(draws):
                    key = severity_map.get(issue.severity.value, issue.severity.value)
                    issues[key].append(issue)

                # Extract pass switch information
                pass_switches = self.pass_switches_detector.extract_switch_info(draws)

            except Exception as e:
                errors.append(f"Error in draw analysis: {str(e)}")

        # Run pass duration detector if passes are provided
        if passes:
            try:
                for issue in self.pass_duration_detector.detect(passes):
                    key = severity_map.get(issue.severity.value, issue.severity.value)
                    issues[key].append(issue)
            except Exception as e:
                errors.append(f"Error in pass analysis: {str(e)}")

        # Run Mali complexity detector if enabled
        # Note: Mali analysis requires shader source code, which may not always be available
        try:
            if self.mali_complexity_detector.is_enabled:
                mali_issues = self.mali_complexity_detector.detect(shaders)
                for issue in mali_issues:
                    key = severity_map.get(issue.severity.value, issue.severity.value)
                    issues[key].append(issue)
        except Exception as e:
            # Mali analysis is optional, don't fail the whole analysis
            logger.debug(f"Mali complexity analysis skipped: {str(e)}")

        # Build metrics
        metrics = self._build_metrics(summary, issues, model_stats)

        return AnalysisResult(
            summary=summary,
            issues=issues,
            metrics=metrics,
            errors=errors,
            model_stats=model_stats,
            pass_switches=pass_switches
        )

    def _build_metrics(
        self,
        summary: ReportSummary,
        issues: Dict[str, List],
        model_stats: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Build analysis metrics from summary and issues.

        Args:
            summary: Report summary information
            issues: Issues grouped by severity
            model_stats: Optional model statistics dictionary

        Returns:
            Dictionary containing analysis metrics
        """
        critical_count = len(issues["critical"])
        warning_count = len(issues["warnings"])
        suggestion_count = len(issues["suggestions"])

        metrics = {
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

        # Add model statistics if available
        if model_stats is not None:
            metrics["model_count"] = len(model_stats)
            metrics["model_names"] = list(model_stats.keys())

        return metrics
