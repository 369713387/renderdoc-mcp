# rd_mcp/models.py
from enum import Enum
from pydantic import BaseModel, Field, model_validator
from typing import List, Dict, Any, Optional

class IssueSeverity(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    SUGGESTION = "suggestion"

class Issue(BaseModel):
    """Represents an issue found during RenderDoc analysis."""
    type: str = Field(description="Type identifier for the issue")
    severity: IssueSeverity = Field(description="Severity level of the issue")
    description: str = Field(description="Human-readable description of the issue")
    location: str = Field(description="Location where the issue was detected")
    impact: str = Field(default="medium", description="Performance impact level")

    model_config = {"extra": "forbid"}

class ReportSummary(BaseModel):
    """Summary information from a RenderDoc analysis report."""
    api_type: str = Field(description="Graphics API type (e.g., OpenGL, Vulkan)")
    total_draw_calls: int = Field(description="Total number of draw calls")
    total_shaders: int = Field(description="Total number of shaders")
    frame_count: int = Field(description="Number of frames analyzed")

    model_config = {"extra": "forbid"}


class ModelStats(BaseModel):
    """Statistics for a single model/resource.

    Aggregates draw calls and triangles by inferred model name.
    """
    name: str = Field(description="Model or resource name")
    draw_calls: int = Field(default=0, description="Number of draw calls for this model")
    triangle_count: int = Field(default=0, description="Total triangle count")
    vertex_count: int = Field(default=0, description="Total vertex count")
    passes: List[str] = Field(default_factory=list, description="List of render passes this model appears in")

    model_config = {"extra": "forbid"}


class PassSwitchInfo(BaseModel):
    """Detailed information about pass/framebuffer switches.

    Tracks different types of state changes that cause performance overhead.
    """
    marker_switches: int = Field(default=0, description="Pass marker switches")
    fbo_switches: int = Field(default=0, description="FBO switches")
    texture_bind_changes: int = Field(default=0, description="Texture binding changes")
    shader_changes: int = Field(default=0, description="Shader changes")
    total: int = Field(default=0, description="Calculated total of all switches")

    model_config = {"extra": "forbid"}

    @model_validator(mode='after')
    def calculate_total(self):
        """Calculate total from switches if not explicitly provided."""
        if self.total == 0:
            # If total is 0 (default), calculate from other fields
            self.total = (
                self.marker_switches +
                self.fbo_switches +
                self.texture_bind_changes +
                self.shader_changes
            )
        return self

class AnalysisResult(BaseModel):
    """Complete analysis result containing summary, issues, and metrics."""
    summary: ReportSummary = Field(description="Report summary information")
    issues: Dict[str, List[Issue]] = Field(description="Issues grouped by severity")
    metrics: Dict[str, Any] = Field(description="Analysis metrics")
    errors: List[str] = Field(default_factory=list, description="List of errors encountered during analysis")
    model_stats: Dict[str, ModelStats] = Field(default_factory=dict, description="Statistics for individual models/resources")
    pass_switches: Optional[PassSwitchInfo] = Field(default=None, description="Detailed pass switch information")

    model_config = {"extra": "forbid"}
