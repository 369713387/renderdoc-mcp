# rd_mcp/detectors/shader/mali_complexity.py
"""Mali GPU shader complexity detector using malioc.

This module provides detection of shader complexity issues specifically
for Mali GPUs using the Mali Offline Compiler (malioc) tool.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from rd_mcp.detectors.base import BaseDetector
from rd_mcp.models import Issue, IssueSeverity
from rd_mcp.rdc_analyzer_cmd import ShaderInfo

logger = logging.getLogger(__name__)


@dataclass
class MaliShaderMetrics:
    """Metrics for a shader analyzed by malioc.
    
    Contains performance metrics specific to Mali GPU architecture
    including cycle counts, register usage, and instruction breakdown.
    """
    shader_name: str
    stage: str  # Vertex, Fragment, Compute
    
    # Cycle counts (primary performance indicators)
    total_cycles: float = 0.0
    shortest_path_cycles: float = 0.0
    longest_path_cycles: float = 0.0
    
    # Arithmetic/Logic Unit metrics
    arithmetic_cycles: float = 0.0
    load_store_cycles: float = 0.0
    texture_cycles: float = 0.0
    varying_cycles: float = 0.0
    
    # Register usage (affects occupancy)
    work_registers: int = 0
    uniform_registers: int = 0
    stack_spilling: bool = False
    
    # Instruction counts by type
    total_instructions: int = 0
    arithmetic_instructions: int = 0
    load_store_instructions: int = 0
    texture_instructions: int = 0
    branch_instructions: int = 0
    
    # Texture sampling
    texture_samples: int = 0
    
    # Source info
    has_source: bool = False
    source_lines: int = 0
    
    # Raw malioc output for reference
    raw_output: str = ""
    
    @property
    def is_complex(self) -> bool:
        """Check if shader is considered complex based on common thresholds."""
        return self.total_cycles > 50 or self.work_registers > 32


@dataclass
class MaliAnalysisResult:
    """Complete Mali shader analysis result for a frame."""
    shaders: List[MaliShaderMetrics] = field(default_factory=list)
    malioc_available: bool = False
    malioc_version: str = ""
    target_gpu: str = ""
    errors: List[str] = field(default_factory=list)
    
    @property
    def total_shaders_analyzed(self) -> int:
        return len(self.shaders)
    
    @property
    def complex_shaders(self) -> List[MaliShaderMetrics]:
        """Get list of complex shaders."""
        return [s for s in self.shaders if s.is_complex]
    
    @property
    def fragment_shaders(self) -> List[MaliShaderMetrics]:
        """Get fragment shaders (most performance critical)."""
        return [s for s in self.shaders if s.stage.lower() == "fragment"]
    
    def get_slowest_shaders(self, count: int = 5) -> List[MaliShaderMetrics]:
        """Get the N slowest shaders by total cycle count."""
        return sorted(self.shaders, key=lambda s: s.total_cycles, reverse=True)[:count]


class MaliComplexityDetector(BaseDetector):
    """Detector for Mali GPU shader complexity issues.
    
    Uses the Mali Offline Compiler (malioc) to analyze shader performance
    and detect potential issues like:
    - High cycle count shaders
    - Excessive register usage (causing low occupancy)
    - Heavy texture sampling
    - Stack spilling
    - Branching complexity
    
    Attributes:
        thresholds: Dict containing Mali-specific thresholds:
            - mali_max_cycles: Maximum acceptable total cycles (default: 50)
            - mali_max_registers: Maximum work registers before warning (default: 32)
            - mali_max_texture_samples: Maximum texture samples (default: 8)
            - mali_max_branches: Maximum branch instructions (default: 10)
            - mali_target_gpu: Target GPU for analysis (default: "Mali-G78")
    """
    
    # Default threshold values for Mali analysis
    # mali_enabled defaults to False to avoid showing malioc not found 
    # messages for users who don't need Mali GPU analysis
    DEFAULT_THRESHOLDS = {
        "mali_max_cycles": 50,
        "mali_max_registers": 32,
        "mali_max_texture_samples": 8,
        "mali_max_branches": 10,
        "mali_target_gpu": "Mali-G78",
        "mali_enabled": False,  # Must be explicitly enabled
    }
    
    def __init__(self, thresholds: Dict[str, Any]):
        """Initialize the Mali complexity detector.
        
        Args:
            thresholds: Configuration thresholds including Mali-specific settings
        """
        super().__init__(thresholds)
        
        # Merge with defaults
        self._mali_thresholds = {**self.DEFAULT_THRESHOLDS}
        for key, value in thresholds.items():
            if key.startswith("mali_"):
                self._mali_thresholds[key] = value
        
        # Runner will be lazily initialized
        self._runner = None
        self._malioc_checked = False
        self._malioc_available = False
    
    @property
    def name(self) -> str:
        return "mali_complexity"
    
    @property
    def is_enabled(self) -> bool:
        """Check if Mali analysis is enabled."""
        return self._mali_thresholds.get("mali_enabled", False)
    
    @property
    def target_gpu(self) -> str:
        """Get target GPU for analysis."""
        return self._mali_thresholds.get("mali_target_gpu", "Mali-G78")
    
    def _get_runner(self):
        """Lazily initialize and return the malioc runner."""
        if self._runner is None:
            from rd_mcp.detectors.shader.malioc_runner import MaliocRunner
            self._runner = MaliocRunner()
        return self._runner
    
    def _check_malioc_available(self) -> bool:
        """Check if malioc is available on the system."""
        if not self._malioc_checked:
            try:
                runner = self._get_runner()
                self._malioc_available = runner.is_available()
            except Exception as e:
                logger.warning(f"Failed to check malioc availability: {e}")
                self._malioc_available = False
            self._malioc_checked = True
        return self._malioc_available
    
    def detect(self, data: Any) -> List[Issue]:
        """Detect Mali shader complexity issues.
        
        Args:
            data: Either a MaliAnalysisResult or Dict[str, ShaderInfo]
                  If ShaderInfo dict is provided, malioc analysis will be run
        
        Returns:
            List of Issue objects for detected problems
        """
        if not self.is_enabled:
            return []
        
        issues = []
        
        # Handle different input types
        if isinstance(data, MaliAnalysisResult):
            analysis_result = data
        elif isinstance(data, dict):
            # Assume it's Dict[str, ShaderInfo] - analyze shaders
            analysis_result = self._analyze_shaders(data)
        else:
            logger.warning(f"Unexpected data type for Mali detector: {type(data)}")
            return []
        
        # Check if malioc was available
        if not analysis_result.malioc_available:
            logger.info("malioc not available, skipping Mali complexity detection")
            # Return a helpful suggestion to users about malioc
            issues.append(Issue(
                type="mali_malioc_not_found",
                severity=IssueSeverity.SUGGESTION,
                description=(
                    "Mali Offline Compiler (malioc) 未安装或未配置。"
                    "如需进行Mali GPU着色器复杂度分析，请安装ARM Mobile Studio并设置 MALIOC_PATH 环境变量，"
                    "或在配置文件中指定 malioc_path。"
                ),
                location="Configuration",
                impact="low"
            ))
            return issues
        
        # Report any analysis errors as suggestions
        for error in analysis_result.errors:
            issues.append(Issue(
                type="mali_analysis_warning",
                severity=IssueSeverity.SUGGESTION,
                description=f"Mali分析警告: {error}",
                location="Shader Analysis",
                impact="low"
            ))
        
        # Detect issues for each shader
        for metrics in analysis_result.shaders:
            issues.extend(self._detect_shader_issues(metrics))
        
        # Add summary issue if many complex shaders
        complex_count = len(analysis_result.complex_shaders)
        if complex_count > 3:
            issues.append(Issue(
                type="mali_many_complex_shaders",
                severity=IssueSeverity.WARNING,
                description=(
                    f"发现 {complex_count} 个复杂着色器，"
                    f"可能影响Mali GPU性能"
                ),
                location="Frame",
                impact="high"
            ))
        
        return issues
    
    def _analyze_shaders(self, shaders: Dict[str, Any]) -> MaliAnalysisResult:
        """Analyze shaders using malioc.
        
        Args:
            shaders: Dictionary mapping shader names to ShaderInfo objects or dicts.
                     If dict, expects keys: 'source', 'stage' (optional: 'instruction_count')
            
        Returns:
            MaliAnalysisResult with analyzed metrics
        """
        result = MaliAnalysisResult()
        
        if not self._check_malioc_available():
            result.malioc_available = False
            return result
        
        result.malioc_available = True
        runner = self._get_runner()
        result.malioc_version = runner.get_version()
        result.target_gpu = self.target_gpu
        
        for shader_name, shader_data in shaders.items():
            # Support both ShaderInfo objects and dict format
            if isinstance(shader_data, dict):
                source = shader_data.get('source')
                stage = shader_data.get('stage', 'Unknown')
            else:
                # ShaderInfo object
                source = getattr(shader_data, 'source', None)
                stage = getattr(shader_data, 'stage', 'Unknown')
            
            if not source:
                logger.debug(f"Skipping shader {shader_name}: no source available")
                continue
            
            try:
                metrics = runner.analyze_shader(
                    source=source,
                    stage=stage,
                    shader_name=shader_name,
                    target_gpu=self.target_gpu
                )
                if metrics:
                    result.shaders.append(metrics)
            except Exception as e:
                error_msg = f"Failed to analyze shader {shader_name}: {e}"
                logger.warning(error_msg)
                result.errors.append(error_msg)
        
        return result
    
    def _detect_shader_issues(self, metrics: MaliShaderMetrics) -> List[Issue]:
        """Detect issues for a single shader's metrics.
        
        Args:
            metrics: MaliShaderMetrics for the shader
            
        Returns:
            List of issues found
        """
        issues = []
        shader_location = f"Shader: {metrics.shader_name} ({metrics.stage})"
        
        # Check cycle count
        max_cycles = self._mali_thresholds["mali_max_cycles"]
        if metrics.total_cycles > max_cycles:
            severity = IssueSeverity.CRITICAL if metrics.total_cycles > max_cycles * 2 else IssueSeverity.WARNING
            issues.append(Issue(
                type="mali_high_cycle_count",
                severity=severity,
                description=(
                    f"着色器周期数过高 ({metrics.total_cycles:.1f} cycles)，"
                    f"超过阈值 {max_cycles}。"
                    f"算术: {metrics.arithmetic_cycles:.1f}, "
                    f"纹理: {metrics.texture_cycles:.1f}, "
                    f"加载/存储: {metrics.load_store_cycles:.1f}"
                ),
                location=shader_location,
                impact="high"
            ))
        
        # Check register usage
        max_registers = self._mali_thresholds["mali_max_registers"]
        if metrics.work_registers > max_registers:
            issues.append(Issue(
                type="mali_high_register_usage",
                severity=IssueSeverity.WARNING,
                description=(
                    f"工作寄存器使用过多 ({metrics.work_registers})，"
                    f"超过阈值 {max_registers}。这会降低GPU占用率"
                ),
                location=shader_location,
                impact="medium"
            ))
        
        # Check stack spilling
        if metrics.stack_spilling:
            issues.append(Issue(
                type="mali_stack_spilling",
                severity=IssueSeverity.WARNING,
                description=(
                    f"着色器发生栈溢出(stack spilling)，"
                    f"表示寄存器压力过大"
                ),
                location=shader_location,
                impact="medium"
            ))
        
        # Check texture samples
        max_samples = self._mali_thresholds["mali_max_texture_samples"]
        if metrics.texture_samples > max_samples:
            issues.append(Issue(
                type="mali_excessive_texture_samples",
                severity=IssueSeverity.WARNING,
                description=(
                    f"纹理采样次数过多 ({metrics.texture_samples})，"
                    f"超过阈值 {max_samples}"
                ),
                location=shader_location,
                impact="medium"
            ))
        
        # Check branching
        max_branches = self._mali_thresholds["mali_max_branches"]
        if metrics.branch_instructions > max_branches:
            issues.append(Issue(
                type="mali_excessive_branching",
                severity=IssueSeverity.SUGGESTION,
                description=(
                    f"分支指令过多 ({metrics.branch_instructions})，"
                    f"超过阈值 {max_branches}。考虑使用无分支算法"
                ),
                location=shader_location,
                impact="low"
            ))
        
        return issues
    
    def analyze_shaders(self, shaders: Dict[str, ShaderInfo]) -> MaliAnalysisResult:
        """Public method to analyze shaders and get full results.
        
        This method is useful when you want the full MaliAnalysisResult
        rather than just the detected issues.
        
        Args:
            shaders: Dictionary mapping shader names to ShaderInfo
            
        Returns:
            MaliAnalysisResult with complete analysis data
        """
        return self._analyze_shaders(shaders)
