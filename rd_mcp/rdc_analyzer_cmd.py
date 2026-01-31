# rd_mcp/rdc_analyzer_cmd.py
"""RDC file analyzer using renderdoccmd (XML-based).

This module provides RDC analysis functionality by converting .rdc files
to XML using renderdoccmd and parsing the XML to extract performance data.
"""
import gc
import logging
import os
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from collections import Counter, OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from rd_mcp.detectors.shader.mali_complexity import MaliAnalysisResult

logger = logging.getLogger(__name__)

# Try to find renderdoccmd
RENDERDOC_CMD_PATHS = [
    r"C:\Program Files\RenderDoc\renderdoccmd.exe",
    r"C:\Program Files (x86)\RenderDoc\renderdoccmd.exe",
]


def find_renderdoccmd() -> Optional[str]:
    """Find the renderdoccmd executable.

    Returns:
        Path to renderdoccmd.exe, or None if not found
    """
    for path in RENDERDOC_CMD_PATHS:
        if Path(path).exists():
            return path
    return None


@dataclass
class RDCSummary:
    """Summary information extracted from RDC file."""
    api_type: str
    gpu_name: str
    total_draw_calls: int
    total_shaders: int
    frame_count: int = 1
    resolution: str = ""


@dataclass
class DrawCallInfo:
    """Information about a single draw call."""
    draw_id: int
    event_id: int
    name: str
    duration_ns: int = 0
    vertex_count: int = 0
    marker: str = ""

    @property
    def gpu_duration_ms(self) -> float:
        return self.duration_ns / 1_000_000.0


@dataclass
class ShaderInfo:
    """Information about a shader."""
    name: str
    stage: str
    instruction_count: int = 0
    source_length: int = 0
    source: str = ""
    binding_count: int = 0  # Added for compatibility with rdc_analyzer.py


@dataclass
class TextureInfo:
    """Information about a texture resource."""
    resource_id: str
    name: str
    width: int = 0
    height: int = 0
    depth: int = 1  # Added for compatibility with rdc_analyzer.py
    format: str = ""


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


class RDCAnalyzerCMD:
    """Analyzer for RenderDoc capture files using renderdoccmd.

    This class provides methods to analyze .rdc files by converting them
    to XML using renderdoccmd and parsing the XML output.
    """

    def __init__(self, renderdoccmd_path: Optional[str] = None):
        """Initialize the RDC analyzer.

        Args:
            renderdoccmd_path: Optional path to renderdoccmd.exe.
                             If None, searches standard locations.

        Raises:
            RuntimeError: If renderdoccmd is not found
        """
        self.renderdoccmd = renderdoccmd_path or find_renderdoccmd()
        if not self.renderdoccmd:
            raise RuntimeError(
                "renderdoccmd.exe not found. Please install RenderDoc from "
                "https://renderdoc.org/"
            )
        self._temp_dir: Optional[tempfile.TemporaryDirectory] = None

    def __del__(self):
        """Cleanup temporary files."""
        if self._temp_dir:
            self._temp_dir.cleanup()

    def analyze_file(self, rdc_path: str | Path) -> RDCAnalysisData:
        """Analyze a RenderDoc capture file.

        Args:
            rdc_path: Path to the .rdc capture file

        Returns:
            RDCAnalysisData containing extracted information

        Raises:
            FileNotFoundError: If the RDC file doesn't exist
            RuntimeError: If analysis fails
        """
        rdc_path = Path(rdc_path)
        if not rdc_path.exists():
            raise FileNotFoundError(f"RDC file not found: {rdc_path}")

        # Create temp directory
        self._temp_dir = tempfile.TemporaryDirectory()
        xml_path = Path(self._temp_dir.name) / "output.xml"

        # Convert RDC to XML
        self._convert_to_xml(rdc_path, xml_path)

        # Parse XML
        try:
            return self._parse_xml(xml_path)
        finally:
            # Cleanup
            gc.collect()

    def _convert_to_xml(self, rdc_path: Path, xml_path: Path) -> None:
        """Convert RDC file to XML using renderdoccmd.

        Args:
            rdc_path: Path to input .rdc file
            xml_path: Path to output XML file

        Raises:
            RuntimeError: If conversion fails
        """
        cmd = [
            self.renderdoccmd,
            "convert",
            "-f", str(rdc_path),
            "-o", str(xml_path),
            "-c", "xml"
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='ignore',
                timeout=120  # 2 minute timeout
            )

            if result.returncode != 0:
                raise RuntimeError(
                    f"renderdoccmd failed: {result.stderr}\n{result.stdout}"
                )

            if not xml_path.exists():
                raise RuntimeError(f"XML output not created: {xml_path}")

        except subprocess.TimeoutExpired:
            raise RuntimeError("RDC conversion timed out (file may be too large)")
        except FileNotFoundError:
            raise RuntimeError(f"renderdoccmd not found at: {self.renderdoccmd}")

    def _parse_xml(self, xml_path: Path) -> RDCAnalysisData:
        """Parse the converted XML file.

        Args:
            xml_path: Path to the XML file

        Returns:
            RDCAnalysisData with extracted information
        """
        tree = ET.parse(xml_path)
        root = tree.getroot()

        # Extract summary
        summary = self._extract_summary(root)

        # Extract draws
        draws = self._extract_draws(root)

        # Extract shaders
        shaders = self._extract_shaders(root)

        # Extract textures (from API calls)
        textures = self._extract_textures(root)

        # Group into passes
        passes = self._extract_passes(draws)

        return RDCAnalysisData(
            summary=summary,
            draws=draws,
            shaders=shaders,
            textures=textures,
            passes=passes
        )

    def _extract_summary(self, root: ET.Element) -> RDCSummary:
        """Extract summary information from XML root.

        Args:
            root: XML root element

        Returns:
            RDCSummary with basic information
        """
        header = root.find("header")
        if header is None:
            return RDCSummary(api_type="Unknown", gpu_name="Unknown",
                            total_draw_calls=0, total_shaders=0)

        # Get API type
        driver_elem = header.find("driver")
        api_type = driver_elem.text if driver_elem is not None else "Unknown"

        # Get GPU name from first chunk
        gpu_name = "Unknown"
        for chunk in root.findall(".//chunk"):
            renderer = chunk.find(".//string[@name='renderer']")
            if renderer is not None and renderer.text:
                gpu_name = renderer.text
                break

        # Get resolution from thumbnail
        thumbnail = header.find("thumbnail")
        resolution = ""
        if thumbnail is not None:
            width = thumbnail.get("width", "")
            height = thumbnail.get("height", "")
            if width and height:
                resolution = f"{width}x{height}"

        return RDCSummary(
            api_type=api_type,
            gpu_name=gpu_name,
            total_draw_calls=0,  # Will be updated later
            total_shaders=0,     # Will be updated later
            resolution=resolution
        )

    def _extract_draws(self, root: ET.Element) -> List[DrawCallInfo]:
        """Extract draw calls from XML.

        Args:
            root: XML root element

        Returns:
            List of DrawCallInfo objects
        """
        draws = []
        draw_patterns = [
            r"glDrawArrays",
            r"glDrawElements",
            r"glDrawElementsInstanced",
            r"glDrawArraysInstanced",
        ]

        draw_id = 0
        for chunk in root.findall(".//chunk"):
            name = chunk.get("name", "")

            # Check if this is a draw call
            if any(re.match(pattern, name) for pattern in draw_patterns):
                draw_id += 1
                event_id = int(chunk.get("id", "0"))
                duration = int(chunk.get("duration", "0"))

                # Extract vertex count if available
                vertex_count = 0
                count_elem = chunk.find(".//int[@name='count']")
                if count_elem is not None:
                    try:
                        vertex_count = int(count_elem.text)
                    except (ValueError, TypeError):
                        pass

                # Extract marker/label
                marker = ""
                label_elem = chunk.find(".//string[@name='Label']")
                if label_elem is not None and label_elem.text:
                    marker = label_elem.text

                draws.append(DrawCallInfo(
                    draw_id=draw_id,
                    event_id=event_id,
                    name=name,
                    duration_ns=duration,
                    vertex_count=vertex_count,
                    marker=marker
                ))

        return draws

    def _extract_shaders(self, root: ET.Element) -> Dict[str, ShaderInfo]:
        """Extract shader information from XML.

        Args:
            root: XML root element

        Returns:
            Dictionary mapping shader names to ShaderInfo objects
        """
        shaders = OrderedDict()
        shader_create_calls = ["glCreateShader", "glCreateShaderProgramEXT"]

        for chunk in root.findall(".//chunk"):
            name = chunk.get("name", "")

            if name in shader_create_calls:
                # Get shader resource ID
                shader_id_elem = chunk.find(".//ResourceId[@name='Shader']")
                if shader_id_elem is None:
                    shader_id_elem = chunk.find(".//ResourceId[@name='Program']")

                if shader_id_elem is not None:
                    # Get label
                    label = ""
                    label_elem = chunk.find(".//string[@name='Label']")
                    if label_elem is not None and label_elem.text:
                        label = label_elem.text

                    # Determine shader type
                    type_elem = chunk.find(".//enum[@name='type']")
                    stage = "Unknown"
                    if type_elem is not None:
                        type_str = type_elem.get("string", "")
                        if "VERTEX" in type_str or "vertex" in type_str:
                            stage = "Vertex"
                        elif "FRAGMENT" in type_str or "fragment" in type_str:
                            stage = "Fragment"
                        elif "COMPUTE" in type_str or "compute" in type_str:
                            stage = "Compute"
                        elif "GEOMETRY" in type_str:
                            stage = "Geometry"

                    # Look for shader source in related chunks
                    source_length = 0
                    source = ""

                    # Find the shader source chunk (usually glShaderSource)
                    shader_id = shader_id_elem.text
                    for src_chunk in root.findall(".//chunk"):
                        src_name = src_chunk.get("name", "")
                        if src_name == "glShaderSource":
                            src_shader_elem = src_chunk.find(".//ResourceId[@name='shader']")
                            if src_shader_elem is not None and src_shader_elem.text == shader_id:
                                # Found the shader source chunk
                                source_elem = src_chunk.find(".//array/string")
                                if source_elem is not None and source_elem.text:
                                    source = source_elem.text
                                    source_length = len(source)
                                break

                    shader_name = label or f"Shader_{shader_id}"

                    shaders[shader_name] = ShaderInfo(
                        name=shader_name,
                        stage=stage,
                        instruction_count=0,  # Not available in XML
                        source_length=source_length,
                        source=source
                    )

        return shaders

    def _extract_textures(self, root: ET.Element) -> List[TextureInfo]:
        """Extract texture information from XML.

        Args:
            root: XML root element

        Returns:
            List of TextureInfo objects
        """
        textures = []

        # Look for glTexImage2D, glTexImage3D, glTexStorage2D, etc.
        texture_calls = ["glTexImage2D", "glTexImage3D", "glTexStorage2D",
                        "glTexStorage3D", "glTexImage2DMultisample"]

        for chunk in root.findall(".//chunk"):
            name = chunk.get("name", "")

            if any(tc in name for tc in texture_calls):
                # Try to extract dimensions
                width = 0
                height = 0

                width_elem = chunk.find(".//int[@name='width']")
                if width_elem is not None:
                    try:
                        width = int(width_elem.text)
                    except (ValueError, TypeError):
                        pass

                height_elem = chunk.find(".//int[@name='height']")
                if height_elem is not None:
                    try:
                        height = int(height_elem.text)
                    except (ValueError, TypeError):
                        pass

                # Get texture format
                format_elem = chunk.find(".//enum[@name='format'] \
                                        or .//enum[@name='internalformat']")
                format_str = ""
                if format_elem is not None:
                    format_str = format_elem.get("string", "")

                textures.append(TextureInfo(
                    resource_id=f"tex_{len(textures)}",
                    name=name,
                    width=width,
                    height=height,
                    format=format_str
                ))

        return textures

    def _extract_passes(self, draws: List[DrawCallInfo]) -> List[PassInfo]:
        """Extract render passes from draw calls.

        Groups draw calls into passes based on markers.

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


def analyze_rdc_file(rdc_path: str | Path,
                    renderdoccmd_path: Optional[str] = None) -> RDCAnalysisData:
    """Convenience function to analyze an RDC file.

    Args:
        rdc_path: Path to the .rdc capture file
        renderdoccmd_path: Optional path to renderdoccmd.exe

    Returns:
        RDCAnalysisData containing extracted information

    Example:
        >>> data = analyze_rdc_file("capture.rdc")
        >>> print(f"Draw calls: {data.summary.total_draw_calls}")
        >>> print(f"API: {data.summary.api_type}")
    """
    analyzer = RDCAnalyzerCMD(renderdoccmd_path)
    data = analyzer.analyze_file(rdc_path)

    # Update summary counts
    data.summary.total_draw_calls = len(data.draws)
    data.summary.total_shaders = len(data.shaders)

    return data


def analyze_rdc_with_mali(
    rdc_path: str | Path,
    renderdoccmd_path: Optional[str] = None,
    mali_enabled: bool = True,
    mali_target_gpu: str = "Mali-G78",
    mali_max_cycles: int = 50,
    mali_max_registers: int = 32,
    mali_malioc_path: Optional[str] = None,
) -> tuple[RDCAnalysisData, Optional["MaliAnalysisResult"]]:
    """Analyze an RDC file with optional Mali GPU shader analysis.
    
    This function extends analyze_rdc_file() with Mali Offline Compiler (malioc)
    integration to provide detailed GPU cycle counts and performance metrics
    for Mali GPUs.
    
    Args:
        rdc_path: Path to the .rdc capture file
        renderdoccmd_path: Optional path to renderdoccmd.exe
        mali_enabled: Whether to run Mali shader analysis (default: True)
        mali_target_gpu: Target Mali GPU for analysis (e.g., "Mali-G78", "Mali-G710")
        mali_max_cycles: Maximum acceptable shader cycles threshold
        mali_max_registers: Maximum work registers threshold
        mali_malioc_path: Optional explicit path to malioc executable
        
    Returns:
        Tuple of (RDCAnalysisData, MaliAnalysisResult or None)
        
    Example:
        >>> data, mali_result = analyze_rdc_with_mali("capture.rdc")
        >>> if mali_result and mali_result.malioc_available:
        ...     for shader in mali_result.get_slowest_shaders(5):
        ...         print(f"{shader.shader_name}: {shader.total_cycles} cycles")
    """
    # First, do standard RDC analysis
    data = analyze_rdc_file(rdc_path, renderdoccmd_path)
    
    mali_result = None
    
    if mali_enabled:
        try:
            from rd_mcp.detectors.shader.mali_complexity import (
                MaliComplexityDetector,
                MaliAnalysisResult
            )
            
            # Build Mali configuration
            mali_config = {
                "mali_enabled": True,
                "mali_target_gpu": mali_target_gpu,
                "mali_max_cycles": mali_max_cycles,
                "mali_max_registers": mali_max_registers,
            }
            
            if mali_malioc_path:
                mali_config["mali_malioc_path"] = mali_malioc_path
            
            # Create detector and analyze shaders
            detector = MaliComplexityDetector(mali_config)
            
            # Filter shaders with source code for Mali analysis
            shaders_with_source = {
                name: shader for name, shader in data.shaders.items()
                if shader.source
            }
            
            if shaders_with_source:
                logger.info(f"Analyzing {len(shaders_with_source)} shaders with Mali Offline Compiler...")
                mali_result = detector.analyze_shaders(shaders_with_source)
                
                if mali_result.malioc_available:
                    logger.info(
                        f"Mali analysis complete: {mali_result.total_shaders_analyzed} shaders analyzed, "
                        f"{len(mali_result.complex_shaders)} complex shaders found"
                    )
                else:
                    logger.warning("malioc not available - Mali analysis skipped")
            else:
                logger.info("No shaders with source code found for Mali analysis")
                mali_result = MaliAnalysisResult()
                mali_result.malioc_available = False
                mali_result.errors.append("No shaders with source code available for analysis")
                
        except ImportError as e:
            logger.warning(f"Failed to import Mali analysis module: {e}")
        except Exception as e:
            logger.error(f"Mali analysis failed: {e}")
            # Return partial result with error
            from rd_mcp.detectors.shader.mali_complexity import MaliAnalysisResult
            mali_result = MaliAnalysisResult()
            mali_result.malioc_available = False
            mali_result.errors.append(f"Analysis failed: {str(e)}")
    
    return data, mali_result
