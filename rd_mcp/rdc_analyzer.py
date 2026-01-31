# rd_mcp/rdc_analyzer.py
"""Direct RDC file analyzer using RenderDoc Python API.

This module provides functionality to analyze RenderDoc capture files (.rdc)
directly without generating intermediate HTML reports. It extracts performance
data, draw calls, shaders, and resources for analysis.
"""
import gc
import math
import os
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import renderdoc as rd
except ImportError:
    rd = None
    _RENDERDOC_AVAILABLE = False
else:
    _RENDERDOC_AVAILABLE = True


@dataclass
class RDCSummary:
    """Summary information extracted directly from RDC file."""
    api_type: str
    total_draw_calls: int
    total_shaders: int
    frame_count: int = 1


@dataclass
class DrawCallInfo:
    """Information about a single draw call."""
    draw_id: int
    event_id: int
    name: str
    gpu_duration_ms: float
    vertex_count: int = 0
    instance_count: int = 0
    index_count: int = 0
    marker: str = ""


@dataclass
class ShaderInfo:
    """Information about a shader."""
    name: str
    stage: str
    instruction_count: int = 0
    binding_count: int = 0
    uniform_count: int = 0


@dataclass
class TextureInfo:
    """Information about a texture resource."""
    resource_id: str
    name: str
    width: int
    height: int
    depth: int
    format: str = ""
    mips: int = 1
    array_size: int = 1


@dataclass
class PassInfo:
    """Information about a render pass."""
    name: str
    draw_calls: List[DrawCallInfo] = field(default_factory=list)
    duration_ms: float = 0.0
    resolution: str = ""

    @property
    def draw_count(self) -> int:
        return len(self.draw_calls)


@dataclass
class RDCAnalysisData:
    """Complete data extracted from RDC file for analysis."""
    summary: RDCSummary
    draws: List[DrawCallInfo]
    shaders: Dict[str, ShaderInfo]
    textures: List[TextureInfo]
    passes: List[PassInfo]


class RDCAnalyzer:
    """Analyzer for RenderDoc capture files.

    This class provides methods to open and analyze .rdc files directly
    using the RenderDoc Python API, extracting performance data without
    generating intermediate HTML reports.
    """

    def __init__(self):
        """Initialize the RDC analyzer.

        Raises:
            ImportError: If RenderDoc Python API is not available
        """
        if not _RENDERDOC_AVAILABLE:
            raise ImportError(
                "RenderDoc Python API is not available. "
                "Install RenderDoc or ensure the Python API is in your path."
            )
        self._controller = None
        self._capture = None
        self._sdfile = None
        self._draw_durations: Dict[int, float] = {}

    def analyze_file(self, rdc_path: str | Path) -> RDCAnalysisData:
        """Analyze a RenderDoc capture file.

        Args:
            rdc_path: Path to the .rdc capture file

        Returns:
            RDCAnalysisData containing extracted information

        Raises:
            FileNotFoundError: If the RDC file doesn't exist
            RuntimeError: If the file cannot be opened or analyzed
        """
        rdc_path = Path(rdc_path)
        if not rdc_path.exists():
            raise FileNotFoundError(f"RDC file not found: {rdc_path}")

        # Open the capture file
        self._open_capture(str(rdc_path))

        try:
            # Fetch GPU counters
            self._fetch_gpu_counters()

            # Get API properties
            api_props = self._controller.GetAPIProperties()
            api_type = str(api_props.pipelineType)

            # Extract data
            draws = self._extract_draw_calls()
            shaders = self._extract_shaders()
            textures = self._extract_textures()
            passes = self._extract_passes(draws)

            # Build summary
            summary = RDCSummary(
                api_type=api_type,
                total_draw_calls=len(draws),
                total_shaders=len(shaders),
                frame_count=1
            )

            return RDCAnalysisData(
                summary=summary,
                draws=draws,
                shaders=shaders,
                textures=textures,
                passes=passes
            )

        finally:
            self._close_capture()

    def _open_capture(self, rdc_path: str) -> None:
        """Open a RenderDoc capture file.

        Args:
            rdc_path: Path to the .rdc file

        Raises:
            RuntimeError: If the file cannot be opened
        """
        # Initialize RenderDoc replay
        rd.InitialiseReplay(rd.GlobalEnvironment(), [])

        # Open the capture file
        self._capture = rd.OpenCaptureFile()
        status = self._capture.OpenFile(rdc_path, '', None)

        if status != rd.ReplayStatus.Succeeded:
            raise RuntimeError(f"Couldn't open file: {rd.ReplayStatus(status).name}")

        # Check if local replay is supported
        if not self._capture.LocalReplaySupport():
            raise RuntimeError("Capture cannot be replayed locally")

        # Initialize the replay controller
        status, self._controller = self._capture.OpenCapture(rd.ReplayOptions(), None)

        if status != rd.ReplayStatus.Succeeded:
            raise RuntimeError(f"Couldn't initialise replay: {rd.ReplayStatus(status).name}")

        # Get structured file
        self._sdfile = self._controller.GetStructuredFile()

    def _close_capture(self) -> None:
        """Close the capture and cleanup resources."""
        if self._controller:
            self._controller.Shutdown()
            self._controller = None

        if self._capture:
            self._capture.Shutdown()
            self._capture = None

        if rd:
            rd.ShutdownReplay()

        # Clear cached data
        self._draw_durations.clear()
        gc.collect()

    def _fetch_gpu_counters(self) -> None:
        """Fetch GPU performance counters.

        Stores draw call durations in _draw_durations dictionary.
        """
        self._draw_durations.clear()

        try:
            counter_type = rd.GPUCounter.EventGPUDuration
            results = self._controller.FetchCounters([counter_type])

            for result in results:
                event_id = result.eventId

                # Get the counter description to determine result type
                counter_desc = self._controller.DescribeCounter(counter_type)

                if counter_desc.resultByteWidth == 4:
                    value = result.value.f
                else:
                    value = result.value.d

                # Convert to milliseconds (typically in nanoseconds)
                self._draw_durations[event_id] = value / 1_000_000.0

        except Exception:
            # GPU counters may not be available for all captures/APIs
            pass

    def _extract_draw_calls(self) -> List[DrawCallInfo]:
        """Extract draw call information from the capture.

        Returns:
            List of DrawCallInfo objects
        """
        draws = []

        def visit_action(action, level=0, marker=""):
            nonlocal draws

            action_name = action.GetName(self._sdfile)

            # Update marker if pushing
            current_marker = marker
            if action.flags & rd.ActionFlags.PushMarker:
                items = action_name.replace('|', ' ').replace('(', ' ').replace(')', ' ')
                items = items.replace('-', ' ').replace('=>', ' ').replace('#', ' ').split()
                current_marker = '_'.join(items) if items else action_name

            # Check if this is a draw call
            if (action.flags & rd.ActionFlags.Drawcall or
                action.flags & rd.ActionFlags.Dispatch or
                action.flags & rd.ActionFlags.Copy):

                # Get GPU duration
                gpu_duration = self._draw_durations.get(action.eventId, 0.0)
                if math.isnan(gpu_duration) or gpu_duration < 0:
                    gpu_duration = 0.0

                # Create draw call info
                draw_info = DrawCallInfo(
                    draw_id=action.actionId,
                    event_id=action.eventId,
                    name=action_name,
                    gpu_duration_ms=gpu_duration,
                    marker=current_marker
                )

                # Try to get draw call statistics
                try:
                    draw_stats = self._controller.GetDrawcallStatistics(action.eventId)
                    if hasattr(draw_stats, 'vertices'):
                        draw_info.vertex_count = draw_stats.vertices or 0
                    if hasattr(draw_stats, 'instances'):
                        draw_info.instance_count = draw_stats.instances or 0
                    if hasattr(draw_stats, 'indices'):
                        draw_info.index_count = draw_stats.indices or 0
                except Exception:
                    pass

                draws.append(draw_info)

            # Recursively visit children
            for child in action.children:
                visit_action(child, level + 1, current_marker)

        # Start from root actions
        root_actions = self._controller.GetRootActions()
        for action in root_actions:
            visit_action(action)

        return draws

    def _extract_shaders(self) -> Dict[str, ShaderInfo]:
        """Extract shader information from the capture.

        Returns:
            Dictionary mapping shader names to ShaderInfo objects
        """
        shaders = OrderedDict()

        try:
            # Get all resources
            resources = self._controller.GetResources()

            for resource in resources:
                # Check if this is a shader resource
                if resource.name and ('shader' in resource.name.lower() or
                                      'vs_' in resource.name.lower() or
                                      'ps_' in resource.name.lower() or
                                      'gs_' in resource.name.lower() or
                                      'hs_' in resource.name.lower() or
                                      'ds_' in resource.name.lower() or
                                      'cs_' in resource.name.lower()):

                    # Create shader info
                    shader_info = ShaderInfo(
                        name=resource.name,
                        stage="Unknown",
                        instruction_count=0,
                        binding_count=0,
                        uniform_count=0
                    )

                    # Try to get more detailed shader information
                    try:
                        # This may fail for some captures
                        shader_reflection = self._controller.GetResourceData(resource.resourceId)
                        if hasattr(shader_reflection, 'instructionCount'):
                            shader_info.instruction_count = shader_reflection.instructionCount
                    except Exception:
                        pass

                    shaders[resource.name] = shader_info

        except Exception:
            pass

        return shaders

    def _extract_textures(self) -> List[TextureInfo]:
        """Extract texture information from the capture.

        Returns:
            List of TextureInfo objects
        """
        textures = []

        try:
            # Get all textures
            texture_list = self._controller.GetTextures()

            for tex in texture_list:
                # Create texture info
                tex_info = TextureInfo(
                    resource_id=str(tex.resourceId),
                    name=tex.name or f"Texture_{tex.resourceId}",
                    width=tex.width,
                    height=tex.height,
                    depth=tex.depth,
                    format=str(tex.format),
                    mips=tex.mips,
                    array_size=tex.arraysize
                )

                textures.append(tex_info)

        except Exception:
            pass

        return textures

    def _extract_passes(self, draws: List[DrawCallInfo]) -> List[PassInfo]:
        """Extract render passes from draw calls.

        Groups draw calls into passes based on markers and state changes.

        Args:
            draws: List of DrawCallInfo objects

        Returns:
            List of PassInfo objects
        """
        passes: List[PassInfo] = []
        current_pass = None
        pass_counter = 0

        for draw in draws:
            # Check if we should start a new pass
            need_new_pass = False

            if current_pass is None:
                need_new_pass = True
            elif draw.marker and current_pass.name != draw.marker:
                need_new_pass = True
            elif current_pass.draw_count >= 100:  # Limit pass size
                need_new_pass = True

            if need_new_pass:
                # Create new pass
                pass_counter += 1
                current_pass = PassInfo(
                    name=draw.marker or f"Pass_{pass_counter}",
                    draw_calls=[],
                    duration_ms=0.0
                )
                passes.append(current_pass)

            # Add draw to current pass
            current_pass.draw_calls.append(draw)
            current_pass.duration_ms += draw.gpu_duration_ms

        return passes


def analyze_rdc_file(rdc_path: str | Path) -> RDCAnalysisData:
    """Convenience function to analyze an RDC file.

    Args:
        rdc_path: Path to the .rdc capture file

    Returns:
        RDCAnalysisData containing extracted information

    Example:
        >>> data = analyze_rdc_file("capture.rdc")
        >>> print(f"Draw calls: {data.summary.total_draw_calls}")
        >>> print(f"Shaders: {data.summary.total_shaders}")
    """
    analyzer = RDCAnalyzer()
    return analyzer.analyze_file(rdc_path)
