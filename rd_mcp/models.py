# rd_mcp/models.py
from enum import Enum
from pydantic import BaseModel
from typing import List, Dict, Any

class IssueSeverity(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    SUGGESTION = "suggestion"

class Issue(BaseModel):
    type: str
    severity: IssueSeverity
    description: str
    location: str
    impact: str = "medium"

class ReportSummary(BaseModel):
    api_type: str
    total_draw_calls: int
    total_shaders: int
    frame_count: int

class AnalysisResult(BaseModel):
    summary: ReportSummary
    issues: Dict[str, List[Issue]]
    metrics: Dict[str, Any]
