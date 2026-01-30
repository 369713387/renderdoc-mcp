# rd_mcp/models.py
from enum import Enum
from pydantic import BaseModel, Field
from typing import List, Dict, Any

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

class AnalysisResult(BaseModel):
    """Complete analysis result containing summary, issues, and metrics."""
    summary: ReportSummary = Field(description="Report summary information")
    issues: Dict[str, List[Issue]] = Field(description="Issues grouped by severity")
    metrics: Dict[str, Any] = Field(description="Analysis metrics")

    model_config = {"extra": "forbid"}
