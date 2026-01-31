from typing import List, Optional, Set
from rd_mcp.detectors.base import BaseDetector
from rd_mcp.models import Issue, IssueSeverity, PassSwitchInfo
from rd_mcp.rdc_analyzer_cmd import DrawCallInfo

class PassSwitchesDetector(BaseDetector):
    """Detector for excessive pass/state switches."""

    @property
    def name(self) -> str:
        return "pass_switches"

    def detect(self, draws: List[DrawCallInfo]) -> List[Issue]:
        """Detect excessive state switches.

        Args:
            draws: List of draw calls

        Returns:
            List of switch issues
        """
        max_switches = self.thresholds.get("max_switches_per_frame", 20)
        switch_info = self.extract_switch_info(draws)

        if switch_info.total > max_switches:
            return [Issue(
                type="pass_switches",
                severity=IssueSeverity.WARNING,
                description=(
                    f"Pass/Framebuffer 切换 {switch_info.total}次，超过阈值 {max_switches}次\n"
                    f"- Marker切换: {switch_info.marker_switches}\n"
                    f"- FBO切换: {switch_info.fbo_switches}\n"
                    f"- 纹理绑定改变: {switch_info.texture_bind_changes}\n"
                    f"- Shader切换: {switch_info.shader_changes}"
                ),
                location="Frame",
                impact="medium"
            )]

        return []

    def extract_switch_info(self, draws: List[DrawCallInfo]) -> PassSwitchInfo:
        """Extract detailed switch information.

        Args:
            draws: List of draw calls

        Returns:
            PassSwitchInfo with breakdown of switch types
        """
        marker_switches = 0
        fbo_switches = 0
        texture_bind_changes = 0
        shader_changes = 0

        last_marker = None
        last_fbo = None
        last_textures: Set[str] = set()
        last_shader = None

        for draw in draws:
            # Marker switch
            if draw.marker != last_marker:
                marker_switches += 1
                last_marker = draw.marker

            # FBO switch (simplified - detect based on patterns)
            current_fbo = self._extract_fbo(draw)
            if current_fbo != last_fbo:
                fbo_switches += 1
                last_fbo = current_fbo

            # Texture bind changes (placeholder - needs actual texture tracking)
            current_textures = self._extract_bound_textures(draw)
            if current_textures != last_textures:
                texture_bind_changes += len(current_textures ^ last_textures)
                last_textures = current_textures

            # Shader switch (placeholder - needs actual shader tracking)
            current_shader = self._get_shader_name(draw)
            if current_shader != last_shader:
                shader_changes += 1
                last_shader = current_shader

        return PassSwitchInfo(
            marker_switches=marker_switches,
            fbo_switches=fbo_switches,
            texture_bind_changes=texture_bind_changes,
            shader_changes=shader_changes
        )

    def _extract_fbo(self, draw: DrawCallInfo) -> Optional[str]:
        """Extract FBO ID from draw call (placeholder)."""
        # In real implementation, parse from draw name or associated state
        return None

    def _extract_bound_textures(self, draw: DrawCallInfo) -> Set[str]:
        """Extract bound texture IDs (placeholder)."""
        # In real implementation, track from XML texture bindings
        return set()

    def _get_shader_name(self, draw: DrawCallInfo) -> Optional[str]:
        """Get shader name from draw call (placeholder)."""
        # In real implementation, track from XML shader bindings
        return None
