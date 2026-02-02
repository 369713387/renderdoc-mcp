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


# ============================================================================
# Render State Data Classes
# ============================================================================

@dataclass
class BlendState:
    """混合状态"""
    enabled: bool = False
    src_rgb: str = "ONE"
    dst_rgb: str = "ZERO"
    src_alpha: str = "ONE"
    dst_alpha: str = "ZERO"
    equation_rgb: str = "FUNC_ADD"
    equation_alpha: str = "FUNC_ADD"


@dataclass
class DepthState:
    """深度状态"""
    test_enabled: bool = False
    write_enabled: bool = True
    func: str = "LESS"


@dataclass
class StencilState:
    """模板状态"""
    enabled: bool = False
    func: str = "ALWAYS"
    ref: int = 0
    mask: int = 0xFF
    fail_op: str = "KEEP"
    depth_fail_op: str = "KEEP"
    pass_op: str = "KEEP"


@dataclass
class CullState:
    """面剔除状态"""
    enabled: bool = False
    mode: str = "BACK"
    front_face: str = "CCW"


@dataclass
class ScissorState:
    """裁剪状态"""
    enabled: bool = False
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0


@dataclass
class DrawCallState:
    """DrawCall 完整渲染状态"""
    blend: BlendState = field(default_factory=BlendState)
    depth: DepthState = field(default_factory=DepthState)
    stencil: StencilState = field(default_factory=StencilState)
    cull: CullState = field(default_factory=CullState)
    scissor: ScissorState = field(default_factory=ScissorState)
    polygon_mode: str = "FILL"
    color_mask: str = "RGBA"


# ============================================================================
# Sampler Data Classes
# ============================================================================

@dataclass
class SamplerInfo:
    """贴图采样器设置"""
    sampler_id: str
    texture_id: str = ""
    texture_name: str = ""
    min_filter: str = "LINEAR"
    mag_filter: str = "LINEAR"
    wrap_s: str = "REPEAT"
    wrap_t: str = "REPEAT"
    wrap_r: str = "REPEAT"
    anisotropy: float = 1.0
    min_lod: float = -1000.0
    max_lod: float = 1000.0
    lod_bias: float = 0.0
    compare_mode: str = "NONE"
    compare_func: str = "LEQUAL"


# ============================================================================
# Framebuffer Data Classes
# ============================================================================

@dataclass
class RenderTargetInfo:
    """渲染目标附件信息"""
    attachment: str
    texture_id: str
    texture_name: str = ""
    width: int = 0
    height: int = 0
    format: str = ""
    level: int = 0
    layer: int = 0


@dataclass
class ClearInfo:
    """Clear 操作信息"""
    clear_color: bool = False
    clear_depth: bool = False
    clear_stencil: bool = False
    color_value: tuple = (0.0, 0.0, 0.0, 1.0)
    depth_value: float = 1.0
    stencil_value: int = 0


@dataclass
class FramebufferInfo:
    """帧缓冲区详细配置"""
    fbo_id: str
    name: str = ""
    width: int = 0
    height: int = 0
    color_attachments: List[RenderTargetInfo] = field(default_factory=list)
    depth_attachment: Optional[RenderTargetInfo] = None
    stencil_attachment: Optional[RenderTargetInfo] = None
    depth_stencil_attachment: Optional[RenderTargetInfo] = None
    is_default: bool = False
    draw_buffers: List[str] = field(default_factory=list)
    clear_ops: List[ClearInfo] = field(default_factory=list)


# ============================================================================
# Pass Dependency Data Classes
# ============================================================================

@dataclass
class PassDependency:
    """Pass 之间的资源依赖关系"""
    source_pass: str
    source_pass_index: int
    target_pass: str
    target_pass_index: int
    resource_type: str
    resource_id: str
    resource_name: str = ""
    dependency_type: str = "READ_AFTER_WRITE"


# ============================================================================
# Core Data Classes
# ============================================================================

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
    index_count: int = 0
    instance_count: int = 1
    marker: str = ""
    state: Optional[DrawCallState] = None
    bound_textures: List[str] = field(default_factory=list)
    shader_program: str = ""
    fbo_id: str = ""

    @property
    def gpu_duration_ms(self) -> float:
        return self.duration_ns / 1_000_000.0
    
    @property
    def triangle_count(self) -> int:
        """Estimate triangle count from vertex/index count."""
        count = self.index_count if self.index_count > 0 else self.vertex_count
        return (count // 3) * self.instance_count


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
    depth: int = 1
    format: str = ""
    mip_levels: int = 1
    array_size: int = 1
    samples: int = 1
    memory_size: int = 0  # Estimated memory in bytes
    is_compressed: bool = False
    sampler: Optional[SamplerInfo] = None
    
    @property
    def memory_size_mb(self) -> float:
        """Memory size in megabytes."""
        return self.memory_size / (1024 * 1024)
    
    def estimate_memory(self) -> int:
        """Estimate texture memory usage based on format and dimensions."""
        if self.memory_size > 0:
            return self.memory_size
        
        # Bytes per pixel for common formats
        bpp_map = {
            "RGBA8": 4, "RGB8": 3, "RGBA16F": 8, "RGBA32F": 16,
            "R8": 1, "RG8": 2, "R16F": 2, "RG16F": 4,
            "DEPTH24_STENCIL8": 4, "DEPTH32F": 4, "DEPTH16": 2,
            "ASTC_4x4": 1, "ASTC_6x6": 0.89, "ASTC_8x8": 0.5,
            "ETC2_RGB": 0.5, "ETC2_RGBA": 1,
        }
        
        bpp = 4  # Default to RGBA8
        for fmt, b in bpp_map.items():
            if fmt in self.format.upper():
                bpp = b
                break
        
        # Calculate base size
        base_size = self.width * self.height * self.depth * bpp
        
        # Account for mip levels (roughly 1.33x for full mip chain)
        if self.mip_levels > 1:
            base_size = int(base_size * 1.33)
        
        # Account for array/cubemap
        base_size *= self.array_size
        
        self.memory_size = int(base_size)
        return self.memory_size


@dataclass
class PassInfo:
    """Information about a render pass."""
    name: str
    pass_index: int = 0
    draw_calls: List[DrawCallInfo] = field(default_factory=list)
    duration_ms: float = 0.0
    resolution: str = ""
    fbo_id: str = ""
    input_textures: List[str] = field(default_factory=list)
    output_textures: List[str] = field(default_factory=list)

    @property
    def draw_count(self) -> int:
        return len(self.draw_calls)
    
    @property
    def triangle_count(self) -> int:
        return sum(d.triangle_count for d in self.draw_calls)


@dataclass
class RDCAnalysisData:
    """Complete data extracted from RDC file for analysis."""
    summary: RDCSummary
    draws: List[DrawCallInfo]
    shaders: Dict[str, ShaderInfo]
    textures: List[TextureInfo]
    passes: List[PassInfo]
    # Extended data
    samplers: List[SamplerInfo] = field(default_factory=list)
    framebuffers: Dict[str, FramebufferInfo] = field(default_factory=dict)
    pass_dependencies: List[PassDependency] = field(default_factory=list)


# ============================================================================
# Render State Tracker
# ============================================================================

class RenderStateTracker:
    """追踪 OpenGL 渲染状态变化，重建每个 DrawCall 的完整状态"""
    
    # OpenGL capability to state mapping
    GL_CAPABILITIES = {
        "GL_BLEND": "blend",
        "GL_DEPTH_TEST": "depth_test",
        "GL_STENCIL_TEST": "stencil",
        "GL_CULL_FACE": "cull",
        "GL_SCISSOR_TEST": "scissor",
        "GL_DEPTH_WRITEMASK": "depth_write",
    }
    
    # Blend function mappings
    BLEND_FUNCS = {
        "GL_ZERO": "ZERO", "GL_ONE": "ONE",
        "GL_SRC_COLOR": "SRC_COLOR", "GL_ONE_MINUS_SRC_COLOR": "ONE_MINUS_SRC_COLOR",
        "GL_DST_COLOR": "DST_COLOR", "GL_ONE_MINUS_DST_COLOR": "ONE_MINUS_DST_COLOR",
        "GL_SRC_ALPHA": "SRC_ALPHA", "GL_ONE_MINUS_SRC_ALPHA": "ONE_MINUS_SRC_ALPHA",
        "GL_DST_ALPHA": "DST_ALPHA", "GL_ONE_MINUS_DST_ALPHA": "ONE_MINUS_DST_ALPHA",
        "GL_CONSTANT_COLOR": "CONSTANT_COLOR", "GL_ONE_MINUS_CONSTANT_COLOR": "ONE_MINUS_CONSTANT_COLOR",
        "GL_CONSTANT_ALPHA": "CONSTANT_ALPHA", "GL_ONE_MINUS_CONSTANT_ALPHA": "ONE_MINUS_CONSTANT_ALPHA",
        "GL_SRC_ALPHA_SATURATE": "SRC_ALPHA_SATURATE",
    }
    
    # Depth function mappings
    DEPTH_FUNCS = {
        "GL_NEVER": "NEVER", "GL_LESS": "LESS", "GL_EQUAL": "EQUAL",
        "GL_LEQUAL": "LEQUAL", "GL_GREATER": "GREATER", "GL_NOTEQUAL": "NOTEQUAL",
        "GL_GEQUAL": "GEQUAL", "GL_ALWAYS": "ALWAYS",
    }
    
    # Cull mode mappings
    CULL_MODES = {
        "GL_FRONT": "FRONT", "GL_BACK": "BACK", "GL_FRONT_AND_BACK": "FRONT_AND_BACK",
    }
    
    def __init__(self):
        """Initialize tracker with default OpenGL state"""
        self.reset()
    
    def reset(self):
        """Reset to default OpenGL state"""
        self._blend_enabled = False
        self._src_rgb = "ONE"
        self._dst_rgb = "ZERO"
        self._src_alpha = "ONE"
        self._dst_alpha = "ZERO"
        self._equation_rgb = "FUNC_ADD"
        self._equation_alpha = "FUNC_ADD"
        
        self._depth_test_enabled = False
        self._depth_write_enabled = True
        self._depth_func = "LESS"
        
        self._stencil_enabled = False
        self._stencil_func = "ALWAYS"
        self._stencil_ref = 0
        self._stencil_mask = 0xFF
        self._stencil_fail = "KEEP"
        self._stencil_depth_fail = "KEEP"
        self._stencil_pass = "KEEP"
        
        self._cull_enabled = False
        self._cull_mode = "BACK"
        self._front_face = "CCW"
        
        self._scissor_enabled = False
        self._scissor_x = 0
        self._scissor_y = 0
        self._scissor_width = 0
        self._scissor_height = 0
        
        self._polygon_mode = "FILL"
        self._color_mask = "RGBA"
    
    def process_chunk(self, chunk: ET.Element) -> None:
        """Process an API call chunk and update state accordingly"""
        name = chunk.get("name", "")
        
        # Enable/Disable capabilities
        if name == "glEnable":
            cap = self._get_enum_value(chunk, "cap")
            self._enable_capability(cap, True)
        elif name == "glDisable":
            cap = self._get_enum_value(chunk, "cap")
            self._enable_capability(cap, False)
        
        # Blend functions
        elif name == "glBlendFunc":
            sfactor = self._get_enum_value(chunk, "sfactor")
            dfactor = self._get_enum_value(chunk, "dfactor")
            self._src_rgb = self._src_alpha = self.BLEND_FUNCS.get(sfactor, sfactor)
            self._dst_rgb = self._dst_alpha = self.BLEND_FUNCS.get(dfactor, dfactor)
        elif name == "glBlendFuncSeparate":
            self._src_rgb = self.BLEND_FUNCS.get(self._get_enum_value(chunk, "srcRGB"), "ONE")
            self._dst_rgb = self.BLEND_FUNCS.get(self._get_enum_value(chunk, "dstRGB"), "ZERO")
            self._src_alpha = self.BLEND_FUNCS.get(self._get_enum_value(chunk, "srcAlpha"), "ONE")
            self._dst_alpha = self.BLEND_FUNCS.get(self._get_enum_value(chunk, "dstAlpha"), "ZERO")
        elif name == "glBlendEquation":
            eq = self._get_enum_value(chunk, "mode")
            self._equation_rgb = self._equation_alpha = self._parse_blend_equation(eq)
        elif name == "glBlendEquationSeparate":
            self._equation_rgb = self._parse_blend_equation(self._get_enum_value(chunk, "modeRGB"))
            self._equation_alpha = self._parse_blend_equation(self._get_enum_value(chunk, "modeAlpha"))
        
        # Depth functions
        elif name == "glDepthFunc":
            func = self._get_enum_value(chunk, "func")
            self._depth_func = self.DEPTH_FUNCS.get(func, func)
        elif name == "glDepthMask":
            flag = self._get_bool_value(chunk, "flag")
            self._depth_write_enabled = flag
        
        # Stencil functions
        elif name == "glStencilFunc":
            self._stencil_func = self.DEPTH_FUNCS.get(self._get_enum_value(chunk, "func"), "ALWAYS")
            self._stencil_ref = self._get_int_value(chunk, "ref")
            self._stencil_mask = self._get_int_value(chunk, "mask")
        elif name == "glStencilOp":
            self._stencil_fail = self._parse_stencil_op(self._get_enum_value(chunk, "fail"))
            self._stencil_depth_fail = self._parse_stencil_op(self._get_enum_value(chunk, "zfail"))
            self._stencil_pass = self._parse_stencil_op(self._get_enum_value(chunk, "zpass"))
        
        # Culling
        elif name == "glCullFace":
            mode = self._get_enum_value(chunk, "mode")
            self._cull_mode = self.CULL_MODES.get(mode, mode)
        elif name == "glFrontFace":
            mode = self._get_enum_value(chunk, "mode")
            self._front_face = "CW" if "CW" in mode and "CCW" not in mode else "CCW"
        
        # Scissor
        elif name == "glScissor":
            self._scissor_x = self._get_int_value(chunk, "x")
            self._scissor_y = self._get_int_value(chunk, "y")
            self._scissor_width = self._get_int_value(chunk, "width")
            self._scissor_height = self._get_int_value(chunk, "height")
        
        # Color mask
        elif name == "glColorMask":
            r = self._get_bool_value(chunk, "red")
            g = self._get_bool_value(chunk, "green")
            b = self._get_bool_value(chunk, "blue")
            a = self._get_bool_value(chunk, "alpha")
            self._color_mask = f"{'R' if r else ''}{'G' if g else ''}{'B' if b else ''}{'A' if a else ''}" or "NONE"
        
        # Polygon mode
        elif name == "glPolygonMode":
            mode = self._get_enum_value(chunk, "mode")
            if "LINE" in mode:
                self._polygon_mode = "LINE"
            elif "POINT" in mode:
                self._polygon_mode = "POINT"
            else:
                self._polygon_mode = "FILL"
    
    def _enable_capability(self, cap: str, enabled: bool) -> None:
        """Enable or disable an OpenGL capability"""
        if "BLEND" in cap:
            self._blend_enabled = enabled
        elif "DEPTH_TEST" in cap:
            self._depth_test_enabled = enabled
        elif "STENCIL_TEST" in cap:
            self._stencil_enabled = enabled
        elif "CULL_FACE" in cap:
            self._cull_enabled = enabled
        elif "SCISSOR_TEST" in cap:
            self._scissor_enabled = enabled
    
    def _get_enum_value(self, chunk: ET.Element, name: str) -> str:
        """Get enum value from chunk"""
        elem = chunk.find(f".//enum[@name='{name}']")
        if elem is not None:
            return elem.get("string", elem.text or "")
        return ""
    
    def _get_int_value(self, chunk: ET.Element, name: str) -> int:
        """Get integer value from chunk"""
        elem = chunk.find(f".//int[@name='{name}']")
        if elem is not None:
            try:
                return int(elem.text)
            except (ValueError, TypeError):
                pass
        return 0
    
    def _get_bool_value(self, chunk: ET.Element, name: str) -> bool:
        """Get boolean value from chunk"""
        elem = chunk.find(f".//bool[@name='{name}']")
        if elem is not None:
            return elem.text.lower() in ("true", "1", "gl_true")
        # Also check for byte values
        elem = chunk.find(f".//byte[@name='{name}']")
        if elem is not None:
            return elem.text not in ("0", "false", "GL_FALSE")
        return False
    
    def _parse_blend_equation(self, eq: str) -> str:
        """Parse blend equation enum"""
        if "ADD" in eq:
            return "FUNC_ADD"
        elif "SUBTRACT" in eq:
            return "FUNC_REVERSE_SUBTRACT" if "REVERSE" in eq else "FUNC_SUBTRACT"
        elif "MIN" in eq:
            return "MIN"
        elif "MAX" in eq:
            return "MAX"
        return "FUNC_ADD"
    
    def _parse_stencil_op(self, op: str) -> str:
        """Parse stencil operation enum"""
        ops = {
            "GL_KEEP": "KEEP", "GL_ZERO": "ZERO", "GL_REPLACE": "REPLACE",
            "GL_INCR": "INCR", "GL_INCR_WRAP": "INCR_WRAP",
            "GL_DECR": "DECR", "GL_DECR_WRAP": "DECR_WRAP",
            "GL_INVERT": "INVERT",
        }
        return ops.get(op, op)
    
    def get_current_state(self) -> DrawCallState:
        """Create a DrawCallState snapshot of current state"""
        return DrawCallState(
            blend=BlendState(
                enabled=self._blend_enabled,
                src_rgb=self._src_rgb,
                dst_rgb=self._dst_rgb,
                src_alpha=self._src_alpha,
                dst_alpha=self._dst_alpha,
                equation_rgb=self._equation_rgb,
                equation_alpha=self._equation_alpha,
            ),
            depth=DepthState(
                test_enabled=self._depth_test_enabled,
                write_enabled=self._depth_write_enabled,
                func=self._depth_func,
            ),
            stencil=StencilState(
                enabled=self._stencil_enabled,
                func=self._stencil_func,
                ref=self._stencil_ref,
                mask=self._stencil_mask,
                fail_op=self._stencil_fail,
                depth_fail_op=self._stencil_depth_fail,
                pass_op=self._stencil_pass,
            ),
            cull=CullState(
                enabled=self._cull_enabled,
                mode=self._cull_mode,
                front_face=self._front_face,
            ),
            scissor=ScissorState(
                enabled=self._scissor_enabled,
                x=self._scissor_x,
                y=self._scissor_y,
                width=self._scissor_width,
                height=self._scissor_height,
            ),
            polygon_mode=self._polygon_mode,
            color_mask=self._color_mask,
        )


# ============================================================================
# Sampler Tracker
# ============================================================================

class SamplerTracker:
    """追踪纹理采样器设置"""
    
    FILTER_MODES = {
        "GL_NEAREST": "NEAREST",
        "GL_LINEAR": "LINEAR",
        "GL_NEAREST_MIPMAP_NEAREST": "NEAREST_MIPMAP_NEAREST",
        "GL_LINEAR_MIPMAP_NEAREST": "LINEAR_MIPMAP_NEAREST",
        "GL_NEAREST_MIPMAP_LINEAR": "NEAREST_MIPMAP_LINEAR",
        "GL_LINEAR_MIPMAP_LINEAR": "LINEAR_MIPMAP_LINEAR",
    }
    
    WRAP_MODES = {
        "GL_REPEAT": "REPEAT",
        "GL_CLAMP_TO_EDGE": "CLAMP_TO_EDGE",
        "GL_CLAMP_TO_BORDER": "CLAMP_TO_BORDER",
        "GL_MIRRORED_REPEAT": "MIRRORED_REPEAT",
        "GL_MIRROR_CLAMP_TO_EDGE": "MIRROR_CLAMP_TO_EDGE",
    }
    
    def __init__(self):
        self.samplers: Dict[str, SamplerInfo] = {}
        self._current_texture_unit = 0
        self._bound_textures: Dict[int, str] = {}  # unit -> texture_id
    
    def process_chunk(self, chunk: ET.Element) -> None:
        """Process texture/sampler related API calls"""
        name = chunk.get("name", "")
        
        if name == "glActiveTexture":
            unit = self._get_enum_value(chunk, "texture")
            # Parse GL_TEXTURE0, GL_TEXTURE1, etc.
            if unit:
                match = re.search(r"(\d+)$", unit)
                if match:
                    self._current_texture_unit = int(match.group(1))
                elif "TEXTURE0" in unit:
                    self._current_texture_unit = 0
        
        elif name == "glBindTexture":
            tex_id = self._get_resource_id(chunk, "texture")
            if tex_id:
                self._bound_textures[self._current_texture_unit] = tex_id
        
        elif name in ("glTexParameteri", "glTexParameterf", "glSamplerParameteri", "glSamplerParameterf"):
            self._process_tex_param(chunk, name)
    
    def _process_tex_param(self, chunk: ET.Element, call_name: str) -> None:
        """Process texture/sampler parameter setting"""
        pname = self._get_enum_value(chunk, "pname")
        
        # Get the sampler/texture ID
        if "Sampler" in call_name:
            sampler_id = self._get_resource_id(chunk, "sampler")
        else:
            # Use current bound texture
            sampler_id = self._bound_textures.get(self._current_texture_unit, f"tex_unit_{self._current_texture_unit}")
        
        if not sampler_id:
            return
        
        # Get or create sampler info
        if sampler_id not in self.samplers:
            self.samplers[sampler_id] = SamplerInfo(sampler_id=sampler_id)
        
        sampler = self.samplers[sampler_id]
        param_value = self._get_enum_value(chunk, "param")
        
        if "MIN_FILTER" in pname:
            sampler.min_filter = self.FILTER_MODES.get(param_value, param_value)
        elif "MAG_FILTER" in pname:
            sampler.mag_filter = self.FILTER_MODES.get(param_value, param_value)
        elif "WRAP_S" in pname:
            sampler.wrap_s = self.WRAP_MODES.get(param_value, param_value)
        elif "WRAP_T" in pname:
            sampler.wrap_t = self.WRAP_MODES.get(param_value, param_value)
        elif "WRAP_R" in pname:
            sampler.wrap_r = self.WRAP_MODES.get(param_value, param_value)
        elif "MAX_ANISOTROPY" in pname:
            try:
                float_elem = chunk.find(".//float[@name='param']")
                if float_elem is not None:
                    sampler.anisotropy = float(float_elem.text)
            except (ValueError, TypeError):
                pass
    
    def _get_enum_value(self, chunk: ET.Element, name: str) -> str:
        elem = chunk.find(f".//enum[@name='{name}']")
        if elem is not None:
            return elem.get("string", elem.text or "")
        return ""
    
    def _get_resource_id(self, chunk: ET.Element, name: str) -> str:
        elem = chunk.find(f".//ResourceId[@name='{name}']")
        if elem is not None:
            return elem.text or ""
        return ""
    
    def get_all_samplers(self) -> List[SamplerInfo]:
        return list(self.samplers.values())


# ============================================================================
# Framebuffer Tracker
# ============================================================================

class FramebufferTracker:
    """追踪帧缓冲区绑定和配置"""
    
    def __init__(self):
        self.framebuffers: Dict[str, FramebufferInfo] = {}
        self._current_fbo: str = "0"  # Default framebuffer
        self._pending_clear: Optional[ClearInfo] = None
        
        # Initialize default framebuffer
        self.framebuffers["0"] = FramebufferInfo(
            fbo_id="0",
            name="Default Framebuffer",
            is_default=True
        )
    
    def process_chunk(self, chunk: ET.Element) -> None:
        """Process framebuffer related API calls"""
        name = chunk.get("name", "")
        
        if name == "glBindFramebuffer":
            self._process_bind_framebuffer(chunk)
        elif name in ("glFramebufferTexture2D", "glFramebufferTexture"):
            self._process_framebuffer_texture(chunk)
        elif name == "glFramebufferRenderbuffer":
            self._process_framebuffer_renderbuffer(chunk)
        elif name == "glClear":
            self._process_clear(chunk)
        elif name == "glClearColor":
            self._process_clear_color(chunk)
        elif name == "glClearDepthf" or name == "glClearDepth":
            self._process_clear_depth(chunk)
        elif name == "glDrawBuffers":
            self._process_draw_buffers(chunk)
    
    def _process_bind_framebuffer(self, chunk: ET.Element) -> None:
        fbo_id = self._get_resource_id(chunk, "framebuffer")
        if not fbo_id:
            fbo_id = "0"
        
        self._current_fbo = fbo_id
        
        if fbo_id not in self.framebuffers:
            self.framebuffers[fbo_id] = FramebufferInfo(
                fbo_id=fbo_id,
                name=f"FBO_{fbo_id}",
                is_default=(fbo_id == "0")
            )
    
    def _process_framebuffer_texture(self, chunk: ET.Element) -> None:
        attachment = self._get_enum_value(chunk, "attachment")
        texture_id = self._get_resource_id(chunk, "texture")
        level = self._get_int_value(chunk, "level")
        
        if not attachment or not texture_id:
            return
        
        fbo = self.framebuffers.get(self._current_fbo)
        if not fbo:
            return
        
        rt_info = RenderTargetInfo(
            attachment=attachment,
            texture_id=texture_id,
            level=level
        )
        
        if "COLOR" in attachment:
            fbo.color_attachments.append(rt_info)
        elif "DEPTH_STENCIL" in attachment:
            fbo.depth_stencil_attachment = rt_info
        elif "DEPTH" in attachment:
            fbo.depth_attachment = rt_info
        elif "STENCIL" in attachment:
            fbo.stencil_attachment = rt_info
    
    def _process_framebuffer_renderbuffer(self, chunk: ET.Element) -> None:
        attachment = self._get_enum_value(chunk, "attachment")
        renderbuffer_id = self._get_resource_id(chunk, "renderbuffer")
        
        if not attachment or not renderbuffer_id:
            return
        
        fbo = self.framebuffers.get(self._current_fbo)
        if not fbo:
            return
        
        rt_info = RenderTargetInfo(
            attachment=attachment,
            texture_id=f"RB_{renderbuffer_id}"
        )
        
        if "COLOR" in attachment:
            fbo.color_attachments.append(rt_info)
        elif "DEPTH_STENCIL" in attachment:
            fbo.depth_stencil_attachment = rt_info
        elif "DEPTH" in attachment:
            fbo.depth_attachment = rt_info
        elif "STENCIL" in attachment:
            fbo.stencil_attachment = rt_info
    
    def _process_clear(self, chunk: ET.Element) -> None:
        mask = self._get_enum_value(chunk, "mask")
        
        clear_info = ClearInfo(
            clear_color="COLOR" in mask,
            clear_depth="DEPTH" in mask,
            clear_stencil="STENCIL" in mask
        )
        
        fbo = self.framebuffers.get(self._current_fbo)
        if fbo:
            fbo.clear_ops.append(clear_info)
    
    def _process_clear_color(self, chunk: ET.Element) -> None:
        # Store for next clear operation if needed
        pass
    
    def _process_clear_depth(self, chunk: ET.Element) -> None:
        pass
    
    def _process_draw_buffers(self, chunk: ET.Element) -> None:
        fbo = self.framebuffers.get(self._current_fbo)
        if not fbo:
            return
        
        # Parse draw buffers array
        buffers = []
        for enum_elem in chunk.findall(".//enum"):
            name = enum_elem.get("name", "")
            if name.startswith("bufs"):
                buffers.append(enum_elem.get("string", enum_elem.text or ""))
        
        if buffers:
            fbo.draw_buffers = buffers
    
    def _get_enum_value(self, chunk: ET.Element, name: str) -> str:
        elem = chunk.find(f".//enum[@name='{name}']")
        if elem is not None:
            return elem.get("string", elem.text or "")
        return ""
    
    def _get_resource_id(self, chunk: ET.Element, name: str) -> str:
        elem = chunk.find(f".//ResourceId[@name='{name}']")
        if elem is not None:
            return elem.text or ""
        return ""
    
    def _get_int_value(self, chunk: ET.Element, name: str) -> int:
        elem = chunk.find(f".//int[@name='{name}']")
        if elem is not None:
            try:
                return int(elem.text)
            except (ValueError, TypeError):
                pass
        return 0
    
    def get_current_fbo(self) -> str:
        return self._current_fbo
    
    def get_all_framebuffers(self) -> Dict[str, FramebufferInfo]:
        return self.framebuffers


# ============================================================================
# Pass Dependency Analyzer
# ============================================================================

class PassDependencyAnalyzer:
    """分析 Pass 之间的资源依赖关系"""
    
    def __init__(self):
        self.dependencies: List[PassDependency] = []
    
    def analyze(self, passes: List[PassInfo], framebuffers: Dict[str, FramebufferInfo]) -> List[PassDependency]:
        """分析 Pass 之间的依赖关系
        
        检测模式：
        1. Pass A 输出到 FBO 的纹理附件
        2. Pass B 绑定该纹理进行采样
        -> Pass B 依赖 Pass A (READ_AFTER_WRITE)
        """
        self.dependencies = []
        
        # Build output map: texture_id -> (pass_index, pass_name)
        output_map: Dict[str, tuple] = {}
        
        for i, pass_info in enumerate(passes):
            fbo = framebuffers.get(pass_info.fbo_id)
            if fbo:
                for color_att in fbo.color_attachments:
                    output_map[color_att.texture_id] = (i, pass_info.name)
                    pass_info.output_textures.append(color_att.texture_id)
                
                if fbo.depth_attachment:
                    output_map[fbo.depth_attachment.texture_id] = (i, pass_info.name)
                    pass_info.output_textures.append(fbo.depth_attachment.texture_id)
        
        # Check input textures for each pass
        for i, pass_info in enumerate(passes):
            for draw in pass_info.draw_calls:
                for tex_id in draw.bound_textures:
                    if tex_id in output_map:
                        src_index, src_name = output_map[tex_id]
                        if src_index < i:  # Only track forward dependencies
                            pass_info.input_textures.append(tex_id)
                            
                            self.dependencies.append(PassDependency(
                                source_pass=src_name,
                                source_pass_index=src_index,
                                target_pass=pass_info.name,
                                target_pass_index=i,
                                resource_type="TEXTURE",
                                resource_id=tex_id,
                                dependency_type="READ_AFTER_WRITE"
                            ))
        
        return self.dependencies


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

        # Initialize trackers
        state_tracker = RenderStateTracker()
        sampler_tracker = SamplerTracker()
        fbo_tracker = FramebufferTracker()

        # Extract draws with state tracking
        draws = self._extract_draws_with_state(root, state_tracker, sampler_tracker, fbo_tracker)

        # Extract shaders
        shaders = self._extract_shaders(root)

        # Extract textures (from API calls)
        textures = self._extract_textures(root)

        # Group into passes
        passes = self._extract_passes_with_fbo(draws, fbo_tracker)

        # Analyze pass dependencies
        dependency_analyzer = PassDependencyAnalyzer()
        pass_dependencies = dependency_analyzer.analyze(passes, fbo_tracker.get_all_framebuffers())

        return RDCAnalysisData(
            summary=summary,
            draws=draws,
            shaders=shaders,
            textures=textures,
            passes=passes,
            samplers=sampler_tracker.get_all_samplers(),
            framebuffers=fbo_tracker.get_all_framebuffers(),
            pass_dependencies=pass_dependencies
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

    def _extract_draws_with_state(
        self,
        root: ET.Element,
        state_tracker: RenderStateTracker,
        sampler_tracker: SamplerTracker,
        fbo_tracker: FramebufferTracker
    ) -> List[DrawCallInfo]:
        """Extract draw calls from XML with full state tracking.

        Processes all API calls sequentially to track OpenGL state changes
        and capture the complete render state at each draw call.

        Args:
            root: XML root element
            state_tracker: RenderStateTracker instance
            sampler_tracker: SamplerTracker instance
            fbo_tracker: FramebufferTracker instance

        Returns:
            List of DrawCallInfo objects with state information
        """
        draws = []
        draw_patterns = [
            r"glDrawArrays",
            r"glDrawElements",
            r"glDrawElementsInstanced",
            r"glDrawArraysInstanced",
            r"glDrawRangeElements",
            r"glMultiDrawArrays",
            r"glMultiDrawElements",
        ]

        # Track current shader program and bound textures
        current_program = ""
        bound_textures: List[str] = []
        current_texture_unit = 0

        draw_id = 0
        for chunk in root.findall(".//chunk"):
            name = chunk.get("name", "")

            # Update all trackers for each API call
            state_tracker.process_chunk(chunk)
            sampler_tracker.process_chunk(chunk)
            fbo_tracker.process_chunk(chunk)

            # Track shader program binding
            if name == "glUseProgram":
                program_elem = chunk.find(".//ResourceId[@name='program']")
                if program_elem is not None:
                    current_program = program_elem.text or ""

            # Track texture unit switching
            elif name == "glActiveTexture":
                unit_elem = chunk.find(".//enum[@name='texture']")
                if unit_elem is not None:
                    unit_str = unit_elem.get("string", "")
                    match = re.search(r"(\d+)$", unit_str)
                    if match:
                        current_texture_unit = int(match.group(1))

            # Track texture binding
            elif name == "glBindTexture":
                tex_elem = chunk.find(".//ResourceId[@name='texture']")
                if tex_elem is not None:
                    tex_id = tex_elem.text or ""
                    if tex_id:
                        # Ensure list is large enough
                        while len(bound_textures) <= current_texture_unit:
                            bound_textures.append("")
                        bound_textures[current_texture_unit] = tex_id

            # Check if this is a draw call
            if any(re.match(pattern, name) for pattern in draw_patterns):
                draw_id += 1
                event_id = int(chunk.get("id", "0"))
                duration = int(chunk.get("duration", "0"))

                # Extract vertex/index count
                vertex_count = 0
                index_count = 0
                instance_count = 1

                count_elem = chunk.find(".//int[@name='count']")
                if count_elem is not None:
                    try:
                        count_val = int(count_elem.text)
                        if "Elements" in name:
                            index_count = count_val
                        else:
                            vertex_count = count_val
                    except (ValueError, TypeError):
                        pass

                # Extract instance count for instanced draws
                if "Instanced" in name:
                    instance_elem = chunk.find(".//int[@name='instancecount']")
                    if instance_elem is None:
                        instance_elem = chunk.find(".//int[@name='primcount']")
                    if instance_elem is not None:
                        try:
                            instance_count = int(instance_elem.text)
                        except (ValueError, TypeError):
                            pass

                # Extract marker/label
                marker = ""
                label_elem = chunk.find(".//string[@name='Label']")
                if label_elem is not None and label_elem.text:
                    marker = label_elem.text

                # Capture current state snapshot
                current_state = state_tracker.get_current_state()
                current_fbo = fbo_tracker.get_current_fbo()

                # Filter out empty texture bindings
                active_textures = [t for t in bound_textures if t]

                draws.append(DrawCallInfo(
                    draw_id=draw_id,
                    event_id=event_id,
                    name=name,
                    duration_ns=duration,
                    vertex_count=vertex_count,
                    index_count=index_count,
                    instance_count=instance_count,
                    marker=marker,
                    state=current_state,
                    bound_textures=list(active_textures),  # Copy the list
                    shader_program=current_program,
                    fbo_id=current_fbo
                ))

        return draws

    def _extract_passes_with_fbo(
        self,
        draws: List[DrawCallInfo],
        fbo_tracker: FramebufferTracker
    ) -> List[PassInfo]:
        """Extract render passes from draw calls with FBO tracking.

        Groups draw calls into passes based on markers AND framebuffer changes.
        Each FBO switch typically indicates a new render pass.

        Args:
            draws: List of DrawCallInfo objects
            fbo_tracker: FramebufferTracker instance

        Returns:
            List of PassInfo objects with FBO information
        """
        passes: List[PassInfo] = []
        current_pass = None
        pass_counter = 0
        current_fbo = ""

        for draw in draws:
            # Check if we should start a new pass
            need_new_pass = False

            if current_pass is None:
                need_new_pass = True
            # FBO change indicates new pass
            elif draw.fbo_id and draw.fbo_id != current_fbo:
                need_new_pass = True
            # Marker change indicates new pass
            elif draw.marker and current_pass.name != draw.marker:
                need_new_pass = True
            # Large pass threshold
            elif current_pass.draw_count >= 200:
                need_new_pass = True

            if need_new_pass:
                # Create new pass
                pass_counter += 1
                
                # Determine pass name
                if draw.marker:
                    pass_name = draw.marker
                elif draw.fbo_id and draw.fbo_id != "0":
                    fbo_info = fbo_tracker.framebuffers.get(draw.fbo_id)
                    if fbo_info and fbo_info.name:
                        pass_name = fbo_info.name
                    else:
                        pass_name = f"Pass_{pass_counter}_FBO_{draw.fbo_id}"
                else:
                    pass_name = f"Pass_{pass_counter}"

                current_pass = PassInfo(
                    name=pass_name,
                    pass_index=pass_counter - 1,
                    draw_calls=[],
                    duration_ms=0.0,
                    fbo_id=draw.fbo_id
                )
                passes.append(current_pass)
                current_fbo = draw.fbo_id

            # Add draw to current pass
            current_pass.draw_calls.append(draw)
            current_pass.duration_ms += draw.gpu_duration_ms

        # Set pass index for all passes
        for i, p in enumerate(passes):
            p.pass_index = i

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
