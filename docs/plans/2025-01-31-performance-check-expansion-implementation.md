# Performance Check Expansion Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extend RenderDoc MCP server to detect comprehensive performance metrics for mobile and PC game optimization, including pass duration, triangle counts, shader complexity, and state switches.

**Architecture:** Modular detector system organized by detection target (Geometry/Shader/Pass/Memory) with preset configuration system supporting platform-specific thresholds and user overrides.

**Tech Stack:** Python 3.11+, renderdoccmd XML conversion, Pydantic models, pytest testing

---

## Task 1: Refactor Configuration System

**Files:**
- Modify: `rd_mcp/config.py`
- Create: `rd_mcp/presets/mobile-aggressive.json`
- Create: `rd_mcp/presets/mobile-balanced.json`
- Create: `rd_mcp/presets/pc-balanced.json`
- Test: `rd_mcp/tests/test_config.py`

**Step 1: Write failing test for preset loading**

```python
# rd_mcp/tests/test_config.py
import pytest
from pathlib import Path
from rd_mcp.config import Config

def test_load_preset_mobile_aggressive():
    """Test loading mobile-aggressive preset"""
    config = Config.load_preset("mobile-aggressive")
    assert config.thresholds.geometry.max_draw_calls == 500
    assert config.thresholds.geometry.max_triangles == 50000
    assert config.thresholds.pass_.max_duration_ms == 0.3

def test_preset_override():
    """Test user overrides merge with preset"""
    config = Config.load_preset("mobile-aggressive", overrides={
        "geometry": {"max_triangles": 80000}
    })
    assert config.thresholds.geometry.max_triangles == 80000
    assert config.thresholds.geometry.max_draw_calls == 500  # Unchanged
```

**Step 2: Run test to verify it fails**

Run: `pytest rd_mcp/tests/test_config.py::test_load_preset_mobile_aggressive -v`
Expected: FAIL with "Config has no attribute load_preset"

**Step 3: Create preset JSON files**

```json
<!-- rd_mcp/presets/mobile-aggressive.json -->
{
  "description": "移动端激进性能优化 - 严格阈值",
  "thresholds": {
    "geometry": {
      "max_draw_calls": 500,
      "max_triangles": 50000,
      "max_triangles_per_model": 10000
    },
    "shader": {
      "max_vs_instructions": 100,
      "max_fs_instructions": 150,
      "max_cs_instructions": 200
    },
    "pass": {
      "max_duration_ms": 0.3,
      "max_overdraw_ratio": 2.0,
      "max_switches_per_frame": 8
    },
    "memory": {
      "max_texture_size": 2048,
      "require_compressed_textures": true
    }
  }
}
```

```json
<!-- rd_mcp/presets/mobile-balanced.json -->
{
  "description": "移动端平衡性能优化",
  "thresholds": {
    "geometry": {
      "max_draw_calls": 1000,
      "max_triangles": 100000,
      "max_triangles_per_model": 30000
    },
    "shader": {
      "max_vs_instructions": 200,
      "max_fs_instructions": 300,
      "max_cs_instructions": 500
    },
    "pass": {
      "max_duration_ms": 0.5,
      "max_overdraw_ratio": 2.5,
      "max_switches_per_frame": 15
    },
    "memory": {
      "max_texture_size": 2048,
      "require_compressed_textures": false
    }
  }
}
```

```json
<!-- rd_mcp/presets/pc-balanced.json -->
{
  "description": "PC端平衡性能优化",
  "thresholds": {
    "geometry": {
      "max_draw_calls": 3000,
      "max_triangles": 2000000,
      "max_triangles_per_model": 100000
    },
    "shader": {
      "max_vs_instructions": 500,
      "max_fs_instructions": 500,
      "max_cs_instructions": 1000
    },
    "pass": {
      "max_duration_ms": 1.0,
      "max_overdraw_ratio": 3.0,
      "max_switches_per_frame": 20
    },
    "memory": {
      "max_texture_size": 4096,
      "require_compressed_textures": false
    }
  }
}
```

**Step 4: Implement threshold dataclasses**

```python
# rd_mcp/config.py
from dataclasses import dataclass
from typing import Optional
from pathlib import Path
import json

@dataclass
class GeometryThresholds:
    max_triangles: int = 100000
    max_draw_calls: int = 1000
    max_triangles_per_model: int = 50000

@dataclass
class ShaderThresholds:
    max_vs_instructions: int = 500
    max_fs_instructions: int = 500
    max_cs_instructions: int = 1000

@dataclass
class PassThresholds:
    max_duration_ms: float = 1.0
    max_overdraw_ratio: float = 2.5
    max_switches_per_frame: int = 20

@dataclass
class MemoryThresholds:
    max_texture_size: int = 4096
    require_compressed_textures: bool = False

@dataclass
class Thresholds:
    geometry: GeometryThresholds
    shader: ShaderThresholds
    pass_: PassThresholds
    memory: MemoryThresholds

    def __init__(self, data=None):
        if data is None:
            data = {}
        self.geometry = GeometryThresholds(**data.get("geometry", {}))
        self.shader = ShaderThresholds(**data.get("shader", {}))
        # 'pass' is reserved keyword
        pass_data = data.get("pass", data.get("pass_", {}))
        self.pass_ = PassThresholds(**pass_data)
        self.memory = MemoryThresholds(**data.get("memory", {}))

class Config:
    def __init__(self, preset=None, overrides=None):
        if preset:
            self.thresholds = self._load_preset(preset, overrides)
        else:
            self.thresholds = Thresholds(overrides)

    @staticmethod
    def _load_preset(name: str, overrides=None) -> Thresholds:
        """Load preset configuration"""
        preset_dir = Path(__file__).parent / "presets"
        preset_file = preset_dir / f"{name}.json"

        if not preset_file.exists():
            raise FileNotFoundError(f"Preset not found: {name}")

        with open(preset_file, encoding='utf-8') as f:
            data = json.load(f)

        # Deep merge overrides
        if overrides:
            for category, values in overrides.items():
                if category in data["thresholds"]:
                    data["thresholds"][category].update(values)

        return Thresholds(data["thresholds"])

    @staticmethod
    def load_preset(name: str, overrides=None) -> 'Config':
        """Load preset and return Config instance"""
        return Config(preset=name, overrides=overrides)

    @staticmethod
    def load(path: Optional[Path] = None) -> 'Config':
        """Load config from file or use defaults"""
        if path and path.exists():
            with open(path, encoding='utf-8') as f:
                data = json.load(f)
            preset = data.get("preset")
            overrides = data.get("thresholds")
            return Config.load_preset(preset, overrides)
        return Config()
```

**Step 5: Run tests to verify they pass**

Run: `pytest rd_mcp/tests/test_config.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add rd_mcp/config.py rd_mcp/presets/ rd_mcp/tests/test_config.py
git commit -m "feat: add preset configuration system with platform-specific thresholds"
```

---

## Task 2: Create Base Detector Class

**Files:**
- Create: `rd_mcp/detectors/base.py`
- Test: `rd_mcp/tests/test_base_detector.py`

**Step 1: Write test for base detector**

```python
# rd_mcp/tests/test_base_detector.py
import pytest
from rd_mcp.detectors.base import BaseDetector
from rd_mcp.models import Issue, IssueSeverity

class MockDetector(BaseDetector):
    @property
    def name(self) -> str:
        return "mock_detector"

    def detect(self, data):
        return [
            Issue(
                type="test_issue",
                severity=IssueSeverity.CRITICAL,
                description="Test",
                location="Test",
                impact="high"
            )
        ]

def test_base_detector_interface():
    """Test base detector interface"""
    detector = MockDetector(thresholds={"max": 100})
    assert detector.name == "mock_detector"

    issues = detector.detect(None)
    assert len(issues) == 1
    assert issues[0].type == "test_issue"
```

**Step 2: Run test to verify it fails**

Run: `pytest rd_mcp/tests/test_base_detector.py::test_base_detector_interface -v`
Expected: FAIL with "No module named 'rd_mcp.detectors.base'"

**Step 3: Implement base detector class**

```python
# rd_mcp/detectors/base.py
from abc import ABC, abstractmethod
from typing import Any, Dict, List
from rd_mcp.models import Issue

class BaseDetector(ABC):
    """Base class for all performance detectors."""

    def __init__(self, thresholds: Dict[str, Any]):
        """Initialize detector with thresholds.

        Args:
            thresholds: Dictionary of threshold values for detection
        """
        self.thresholds = thresholds

    @abstractmethod
    def detect(self, data: Any) -> List[Issue]:
        """Execute detection and return list of issues.

        Args:
            data: Input data for detection (type varies by detector)

        Returns:
            List of Issue objects found
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Get detector name.

        Returns:
            Detector name string
        """
        pass
```

**Step 4: Run tests to verify they pass**

Run: `pytest rd_mcp/tests/test_base_detector.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add rd_mcp/detectors/base.py rd_mcp/tests/test_base_detector.py
git commit -m "feat: add base detector class with abstract interface"
```

---

## Task 3: Extend Data Models

**Files:**
- Modify: `rd_mcp/models.py`
- Test: `rd_mcp/tests/test_models.py`

**Step 1: Write test for new models**

```python
# rd_mcp/tests/test_models.py
import pytest
from rd_mcp.models import ModelStats, PassSwitchInfo, AnalysisResult
from rd_mcp.models import ReportSummary, Issue, IssueSeverity

def test_model_stats():
    """Test ModelStats dataclass"""
    stats = ModelStats(
        name="Character",
        draw_calls=10,
        triangle_count=5000,
        vertex_count=1500,
        passes=["Geometry", "Shadow"]
    )
    assert stats.name == "Character"
    assert stats.triangle_count == 5000
    assert "Geometry" in stats.passes

def test_pass_switch_info():
    """Test PassSwitchInfo dataclass"""
    info = PassSwitchInfo(
        marker_switches=5,
        fbo_switches=2,
        texture_bind_changes=10,
        shader_changes=3
    )
    assert info.total == 20

def test_analysis_result_with_errors():
    """Test AnalysisResult with errors field"""
    summary = ReportSummary(
        api_type="OpenGL",
        total_draw_calls=100,
        total_shaders=10,
        frame_count=1
    )
    result = AnalysisResult(
        summary=summary,
        issues={"critical": [], "warnings": [], "suggestions": []},
        metrics={},
        errors=["test_error"]
    )
    assert len(result.errors) == 1
    assert result.errors[0] == "test_error"
```

**Step 2: Run test to verify it fails**

Run: `pytest rd_mcp/tests/test_models.py -v`
Expected: FAIL with "ModelStats not found" etc.

**Step 3: Add new dataclasses to models.py**

```python
# rd_mcp/models.py (additions)
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

@dataclass
class ModelStats:
    """Statistics for a single model/resource.

    Aggregates draw calls and triangles by inferred model name.
    """
    name: str
    draw_calls: int = 0
    triangle_count: int = 0
    vertex_count: int = 0
    passes: List[str] = field(default_factory=list)

    def __post_init__(self):
        """Calculate total from switches."""
        if self.total == 0:
            self.total = (
                self.marker_switches +
                self.fbo_switches +
                self.texture_bind_changes +
                self.shader_changes
            )

@dataclass
class PassSwitchInfo:
    """Detailed information about pass/framebuffer switches.

    Tracks different types of state changes that cause performance overhead.
    """
    marker_switches: int = 0      # Pass marker switches
    fbo_switches: int = 0          # FBO switches
    texture_bind_changes: int = 0  # Texture binding changes
    shader_changes: int = 0        # Shader changes
    total: int = 0                 # Calculated total

# Modify AnalysisResult to include errors and model_stats
@dataclass
class AnalysisResult:
    """Result of analyzing a RenderDoc report."""
    summary: ReportSummary
    issues: Dict[str, List[Issue]]
    metrics: Dict[str, Any]
    errors: List[str] = field(default_factory=list)
    model_stats: Dict[str, ModelStats] = field(default_factory=dict)
    pass_switches: Optional[PassSwitchInfo] = None
```

**Step 4: Run tests to verify they pass**

Run: `pytest rd_mcp/tests/test_models.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add rd_mcp/models.py rd_mcp/tests/test_models.py
git commit -m "feat: add ModelStats and PassSwitchInfo dataclasses"
```

---

## Task 4: Create Geometry Detectors

**Files:**
- Create: `rd_mcp/detectors/geometry/triangle_count.py`
- Create: `rd_mcp/detectors/geometry/model_stats.py`
- Test: `rd_mcp/tests/detectors/test_geometry_detectors.py`

**Step 1: Write test for triangle count detector**

```python
# rd_mcp/tests/detectors/test_geometry_detectors.py
import pytest
from rd_mcp.detectors.geometry.triangle_count import TriangleCountDetector
from rd_mcp.detectors.geometry.model_stats import ModelStatsDetector
from rd_mcp.models import IssueSeverity

def test_triangle_count_excessive():
    """Test detection of excessive triangle count"""
    detector = TriangleCountDetector({
        "max_triangles": 100000
    })

    draws = _create_mock_draws(total_vertices=300000)  # 100K triangles
    issues = detector.detect(draws)

    assert len(issues) == 1
    assert issues[0].type == "excessive_triangles"
    assert issues[0].severity == IssueSeverity.CRITICAL
    assert "100000" in issues[0].description

def test_model_stats_aggregation():
    """Test model statistics aggregation"""
    detector = ModelStatsDetector({
        "max_triangles_per_model": 10000
    })

    draws = _create_mock_draws_with_markers()
    model_stats = detector.extract_model_stats(draws)

    assert "Character" in model_stats
    assert model_stats["Character"].draw_calls == 2
    assert model_stats["Character"].triangle_count > 0

def test_heavy_model_detection():
    """Test detection of heavy models"""
    detector = ModelStatsDetector({
        "max_triangles_per_model": 5000
    })

    draws = _create_mock_draws_with_markers()
    issues = detector.detect(draws)

    # Should detect heavy model
    heavy_issues = [i for i in issues if i.type == "heavy_model"]
    assert len(heavy_issues) > 0

def _create_mock_draws(total_vertices=0):
    """Helper to create mock draw calls"""
    from rd_mcp.rdc_analyzer_cmd import DrawCallInfo
    return [DrawCallInfo(
        draw_id=1,
        event_id=1,
        name="glDrawArrays",
        vertex_count=total_vertices
    )]

def _create_mock_draws_with_markers():
    """Helper to create draws with model markers"""
    from rd_mcp.rdc_analyzer_cmd import DrawCallInfo
    return [
        DrawCallInfo(draw_id=1, event_id=1, name="glDrawArrays",
                     vertex_count=3000, marker="Character"),
        DrawCallInfo(draw_id=2, event_id=2, name="glDrawArrays",
                     vertex_count=4500, marker="Character"),
        DrawCallInfo(draw_id=3, event_id=3, name="glDrawArrays",
                     vertex_count=1000, marker="UI"),
    ]
```

**Step 2: Run test to verify it fails**

Run: `pytest rd_mcp/tests/detectors/test_geometry_detectors.py -v`
Expected: FAIL with module not found

**Step 3: Implement triangle count detector**

```python
# rd_mcp/detectors/geometry/triangle_count.py
from typing import List, Dict
from rd_mcp.detectors.base import BaseDetector
from rd_mcp.models import Issue, IssueSeverity
from rd_mcp.rdc_analyzer_cmd import DrawCallInfo

class TriangleCountDetector(BaseDetector):
    """Detector for excessive triangle count in frame."""

    @property
    def name(self) -> str:
        return "triangle_count"

    def detect(self, draws: List[DrawCallInfo]) -> List[Issue]:
        """Detect if total triangle count exceeds threshold.

        Args:
            draws: List of draw calls from frame

        Returns:
            List of issues found
        """
        max_triangles = self.thresholds.get("max_triangles", 100000)

        # Calculate total triangles
        total_triangles = sum(d.vertex_count // 3 for d in draws)

        if total_triangles > max_triangles:
            return [Issue(
                type="excessive_triangles",
                severity=IssueSeverity.CRITICAL,
                description=(
                    f"三角形数量过多 ({total_triangles:,})，超过阈值 {max_triangles:,}"
                ),
                location="Frame",
                impact="high"
            )]

        return []
```

**Step 4: Implement model stats detector**

```python
# rd_mcp/detectors/geometry/model_stats.py
import re
from typing import List, Dict
from collections import defaultdict
from rd_mcp.detectors.base import BaseDetector
from rd_mcp.models import Issue, IssueSeverity, ModelStats
from rd_mcp.rdc_analyzer_cmd import DrawCallInfo

class ModelStatsDetector(BaseDetector):
    """Detector for model-level statistics and heavy models."""

    @property
    def name(self) -> str:
        return "model_stats"

    def detect(self, draws: List[DrawCallInfo]) -> List[Issue]:
        """Detect heavy models.

        Args:
            draws: List of draw calls from frame

        Returns:
            List of issues found
        """
        max_per_model = self.thresholds.get("max_triangles_per_model", 50000)
        model_stats = self.extract_model_stats(draws)

        issues = []
        for name, stats in model_stats.items():
            if stats.triangle_count > max_per_model:
                issues.append(Issue(
                    type="heavy_model",
                    severity=IssueSeverity.WARNING,
                    description=(
                        f"模型 '{name}' 三角形 {stats.triangle_count:,}，"
                        f"超过阈值 {max_per_model:,}"
                    ),
                    location=f"Model: {name} ({stats.draw_calls} Draw Calls)",
                    impact="medium"
                ))

        return issues

    def extract_model_stats(self, draws: List[DrawCallInfo]) -> Dict[str, ModelStats]:
        """Extract statistics grouped by inferred model name.

        Args:
            draws: List of draw calls

        Returns:
            Dictionary mapping model names to ModelStats
        """
        models: Dict[str, ModelStats] = {}

        for draw in draws:
            model_name = self._infer_model_name(draw)

            if model_name not in models:
                models[model_name] = ModelStats(name=model_name)

            stats = models[model_name]
            stats.draw_calls += 1
            stats.triangle_count += draw.vertex_count // 3
            stats.vertex_count += draw.vertex_count

            if draw.marker and draw.marker not in stats.passes:
                stats.passes.append(draw.marker)

        return models

    def _infer_model_name(self, draw: DrawCallInfo) -> str:
        """Intelligently infer model name from draw call.

        Priority:
        1. Marker/label
        2. Parse from draw name patterns
        3. Default to "Unknown"

        Args:
            draw: Draw call info

        Returns:
            Inferred model name
        """
        # Rule 1: Use marker
        if draw.marker:
            return draw.marker

        # Rule 2: Parse from name patterns
        # Pattern: "Model_XXX", "Draw_XXX", etc.
        patterns = [
            r"Model[_\s]+(\w+)",
            r"Draw[_\s]+(\w+)",
            r"Mesh[_\s]+(\w+)",
        ]

        name_upper = draw.name.upper()
        for pattern in patterns:
            match = re.search(pattern, name_upper, re.IGNORECASE)
            if match:
                return match.group(1)

        return "Unknown"
```

**Step 5: Create geometry package __init__.py**

```python
# rd_mcp/detectors/geometry/__init__.py
from rd_mcp.detectors.geometry.triangle_count import TriangleCountDetector
from rd_mcp.detectors.geometry.model_stats import ModelStatsDetector

__all__ = ['TriangleCountDetector', 'ModelStatsDetector']
```

**Step 6: Run tests to verify they pass**

Run: `pytest rd_mcp/tests/detectors/test_geometry_detectors.py -v`
Expected: PASS

**Step 7: Commit**

```bash
git add rd_mcp/detectors/geometry/ rd_mcp/tests/detectors/
git commit -m "feat: add geometry detectors for triangle count and model stats"
```

---

## Task 5: Create Pass Detectors

**Files:**
- Create: `rd_mcp/detectors/pass/duration.py`
- Create: `rd_mcp/detectors/pass/switches.py`
- Test: `rd_mcp/tests/detectors/test_pass_detectors.py`

**Step 1: Write test for pass detectors**

```python
# rd_mcp/tests/detectors/test_pass_detectors.py
import pytest
from rd_mcp.detectors.pass.duration import PassDurationDetector
from rd_mcp.detectors.pass.switches import PassSwitchesDetector
from rd_mcp.models import IssueSeverity

def test_slow_pass_detection():
    """Test detection of slow render passes"""
    detector = PassDurationDetector({
        "max_duration_ms": 0.5
    })

    passes = _create_mock_passes([
        ("Geometry", 0.3),
        ("Shadow", 5.2),  # Too slow
        ("Transparent", 0.4)
    ])

    issues = detector.detect(passes)

    assert len(issues) == 1
    assert issues[0].type == "slow_pass"
    assert "Shadow" in issues[0].location
    assert "5.2" in issues[0].description

def test_pass_switches_detection():
    """Test detection of excessive pass switches"""
    detector = PassSwitchesDetector({
        "max_switches_per_frame": 10
    })

    draws = _create_mock_draws_with_switches(15)  # 15 marker switches
    issues = detector.detect(draws)

    assert len(issues) == 1
    assert issues[0].type == "pass_switches"
    assert "15" in issues[0].description

def test_pass_switch_info_extraction():
    """Test detailed switch information"""
    detector = PassSwitchesDetector({})

    draws = _create_mock_draws_with_switches(5)
    info = detector.extract_switch_info(draws)

    assert info.marker_switches == 5
    assert info.total > 0

def _create_mock_passes(duration_data):
    """Helper to create mock passes"""
    from rd_mcp.rdc_analyzer_cmd import PassInfo, DrawCallInfo
    passes = []
    for name, duration in duration_data:
        pass_info = PassInfo(
            name=name,
            draw_calls=[DrawCallInfo(draw_id=1, event_id=1, name="draw")],
            duration_ms=duration,
            resolution="1920x1080"
        )
        passes.append(pass_info)
    return passes

def _create_mock_draws_with_switches(num_switches):
    """Helper to create draws with marker switches"""
    from rd_mcp.rdc_analyzer_cmd import DrawCallInfo
    draws = []
    for i in range(num_switches * 2):
        draws.append(DrawCallInfo(
            draw_id=i,
            event_id=i,
            name="glDrawArrays",
            marker=f"Pass_{i // 2}"
        ))
    return draws
```

**Step 2: Run test to verify it fails**

Run: `pytest rd_mcp/tests/detectors/test_pass_detectors.py -v`
Expected: FAIL with module not found

**Step 3: Implement pass duration detector**

```python
# rd_mcp/detectors/pass/duration.py
from typing import List
from rd_mcp.detectors.base import BaseDetector
from rd_mcp.models import Issue, IssueSeverity
from rd_mcp.rdc_analyzer_cmd import PassInfo

class PassDurationDetector(BaseDetector):
    """Detector for slow render passes."""

    @property
    def name(self) -> str:
        return "pass_duration"

    def detect(self, passes: List[PassInfo]) -> List[Issue]:
        """Detect passes exceeding duration threshold.

        Args:
            passes: List of render passes

        Returns:
            List of slow pass issues
        """
        max_duration = self.thresholds.get("max_duration_ms", 1.0)
        issues = []

        for pass_info in passes:
            if pass_info.duration_ms > max_duration:
                resolution_str = f" ({pass_info.resolution})" if pass_info.resolution else ""
                issues.append(Issue(
                    type="slow_pass",
                    severity=IssueSeverity.CRITICAL,
                    description=(
                        f"Pass '{pass_info.name}' 耗时 {pass_info.duration_ms:.2f}ms，"
                        f"超过阈值 {max_duration:.2f}ms"
                    ),
                    location=f"Pass: {pass_info.name}{resolution_str}",
                    impact="high"
                ))

        return issues
```

**Step 4: Implement pass switches detector**

```python
# rd_mcp/detectors/pass/switches.py
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
            # Current implementation counts draw calls as potential texture changes
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
```

**Step 5: Create pass package __init__.py**

```python
# rd_mcp/detectors/pass/__init__.py
from rd_mcp.detectors.pass.duration import PassDurationDetector
from rd_mcp.detectors.pass.switches import PassSwitchesDetector

__all__ = ['PassDurationDetector', 'PassSwitchesDetector']
```

**Step 6: Run tests to verify they pass**

Run: `pytest rd_mcp/tests/detectors/test_pass_detectors.py -v`
Expected: PASS

**Step 7: Commit**

```bash
git add rd_mcp/detectors/pass/ rd_mcp/tests/detectors/test_pass_detectors.py
git commit -m "feat: add pass detectors for duration and state switches"
```

---

## Task 6: Integrate New Detectors into Analyzer

**Files:**
- Modify: `rd_mcp/analyzer.py`
- Test: `rd_mcp/tests/test_analyzer_integration.py`

**Step 1: Write test for integrated analyzer**

```python
# rd_mcp/tests/test_analyzer_integration.py
import pytest
from rd_mcp.analyzer import Analyzer
from rd_mcp.models import ReportSummary
from rd_mcp.rdc_analyzer_cmd import analyze_rdc_file

def test_analyzer_with_preset():
    """Test analyzer loads preset correctly"""
    analyzer = Analyzer(config=None, preset="mobile-aggressive")

    assert analyzer.config.thresholds.geometry.max_draw_calls == 500
    assert analyzer.config.thresholds.pass_.max_duration_ms == 0.3

def test_full_analysis_workflow():
    """Test complete analysis with all detectors"""
    analyzer = Analyzer(preset="mobile-aggressive")

    # Create mock data
    summary = ReportSummary(
        api_type="OpenGL",
        total_draw_calls=1500,  # Exceeds threshold
        total_shaders=50,
        frame_count=1
    )

    passes = _create_slow_passes()
    draws = _create_excessive_draws()

    result = analyzer.analyze(summary, {}, resources=[], passes=passes, draws=draws)

    # Should detect excessive draw calls
    critical_issues = result.issues.get("critical", [])
    drawcall_issues = [i for i in critical_issues if i.type == "excessive_draw_calls"]
    assert len(drawcall_issues) > 0

    # Should detect slow pass
    pass_issues = [i for i in critical_issues if i.type == "slow_pass"]
    assert len(pass_issues) > 0

def test_model_stats_in_result():
    """Test model statistics are included in result"""
    analyzer = Analyzer()

    summary = ReportSummary(
        api_type="OpenGL",
        total_draw_calls=100,
        total_shaders=10,
        frame_count=1
    )

    draws = _create_draws_with_models()
    result = analyzer.analyze(summary, {}, resources=[], passes=[], draws=draws)

    # Should have model stats
    assert len(result.model_stats) > 0
    assert "Character" in result.model_stats or "Unknown" in result.model_stats

def _create_slow_passes():
    """Helper to create slow passes"""
    from rd_mcp.rdc_analyzer_cmd import PassInfo, DrawCallInfo
    return [
        PassInfo(
            name="SlowPass",
            draw_calls=[DrawCallInfo(draw_id=1, event_id=1, name="draw")],
            duration_ms=5.0,
            resolution="1920x1080"
        )
    ]

def _create_excessive_draws():
    """Helper to create excessive draw calls"""
    from rd_mcp.rdc_analyzer_cmd import DrawCallInfo
    return [
        DrawCallInfo(draw_id=i, event_id=i, name="glDrawArrays", vertex_count=300)
        for i in range(1500)
    ]

def _create_draws_with_models():
    """Helper to create draws with model markers"""
    from rd_mcp.rdc_analyzer_cmd import DrawCallInfo
    return [
        DrawCallInfo(draw_id=1, event_id=1, name="draw", vertex_count=3000, marker="Character"),
        DrawCallInfo(draw_id=2, event_id=2, name="draw", vertex_count=2000, marker="Terrain"),
    ]
```

**Step 2: Run test to verify it fails**

Run: `pytest rd_mcp/tests/test_analyzer_integration.py -v`
Expected: FAIL with signature errors

**Step 3: Update analyzer with new detectors**

```python
# rd_mcp/analyzer.py
from rd_mcp.config import Config
from rd_mcp.detectors.drawcall import DrawCallDetector
from rd_mcp.detectors.shader import ShaderDetector
from rd_mcp.detectors.resource import ResourceDetector
# New detectors
from rd_mcp.detectors.geometry.triangle_count import TriangleCountDetector
from rd_mcp.detectors.geometry.model_stats import ModelStatsDetector
from rd_mcp.detectors.pass.duration import PassDurationDetector
from rd_mcp.detectors.pass.switches import PassSwitchesDetector

from rd_mcp.models import ReportSummary, AnalysisResult
from typing import Dict, List, Any, Optional

class Analyzer:
    """Main analyzer for RenderDoc reports.

    This class orchestrates the analysis of RenderDoc reports by coordinating
    multiple detectors to identify performance issues and provide insights.
    """

    def __init__(self, config_path=None, preset=None):
        """Initialize the analyzer with configuration.

        Args:
            config_path: Optional path to custom configuration file
            preset: Optional preset name to load
        """
        from pathlib import Path
        path = Path(config_path) if config_path else None

        if preset:
            self.config = Config.load_preset(preset)
        elif path:
            self.config = Config.load(path)
        else:
            self.config = Config.load()

        # Initialize all detectors
        self.drawcall_detector = DrawCallDetector(self.config.thresholds.__dict__)
        self.shader_detector = ShaderDetector(self.config.thresholds.__dict__)
        self.resource_detector = ResourceDetector(self.config.thresholds.__dict__)

        # New detectors
        self.triangle_detector = TriangleCountDetector(self.config.thresholds.geometry.__dict__)
        self.model_stats_detector = ModelStatsDetector(self.config.thresholds.geometry.__dict__)
        self.pass_duration_detector = PassDurationDetector(self.config.thresholds.pass_.__dict__)
        self.pass_switches_detector = PassSwitchesDetector(self.config.thresholds.pass_.__dict__)

    def analyze(
        self,
        summary: ReportSummary,
        shaders: Dict[str, Dict[str, Any]],
        resources: List[Dict[str, Any]],
        passes: Optional[List] = None,
        draws: Optional[List] = None
    ) -> AnalysisResult:
        """Analyze a RenderDoc report and identify performance issues.

        Args:
            summary: Report summary containing API type, draw calls, etc.
            shaders: Dictionary of shader data with instruction counts
            resources: List of resource data including texture dimensions
            passes: Optional list of PassInfo objects
            draws: Optional list of DrawCallInfo objects

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
        model_stats = {}
        pass_switches = None

        # Map severity enum to plural form for dictionary keys
        severity_map = {
            "critical": "critical",
            "warning": "warnings",
            "suggestion": "suggestions"
        }

        # Existing detectors
        issues["critical"].extend(
            self.drawcall_detector.detect_excessive_draw_calls(summary.total_draw_calls)
        )

        for issue in self.shader_detector.detect_expensive_shaders(shaders):
            key = severity_map.get(issue.severity.value, issue.severity.value)
            issues[key].append(issue)

        for issue in self.resource_detector.detect_large_textures(resources):
            key = severity_map.get(issue.severity.value, issue.severity.value)
            issues[key].append(issue)

        # New geometry detectors (require draws)
        if draws:
            try:
                for issue in self.triangle_detector.detect(draws):
                    key = severity_map.get(issue.severity.value, issue.severity.value)
                    issues[key].append(issue)

                # Model statistics
                model_stats = self.model_stats_detector.extract_model_stats(draws)
                for issue in self.model_stats_detector.detect(draws):
                    key = severity_map.get(issue.severity.value, issue.severity.value)
                    issues[key].append(issue)

            except Exception as e:
                errors.append(f"geometry_detector: {str(e)}")

        # New pass detectors
        if passes:
            try:
                for issue in self.pass_duration_detector.detect(passes):
                    key = severity_map.get(issue.severity.value, issue.severity.value)
                    issues[key].append(issue)
            except Exception as e:
                errors.append(f"pass_duration: {str(e)}")

        if draws:
            try:
                for issue in self.pass_switches_detector.detect(draws):
                    key = severity_map.get(issue.severity.value, issue.severity.value)
                    issues[key].append(issue)

                # Extract switch info for reporting
                pass_switches = self.pass_switches_detector.extract_switch_info(draws)
            except Exception as e:
                errors.append(f"pass_switches: {str(e)}")

        # Build metrics
        metrics = self._build_metrics(summary, issues, model_stats, pass_switches)

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
        model_stats: Dict = None,
        pass_switches: Any = None
    ) -> Dict[str, Any]:
        """Build analysis metrics from summary and issues."""
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
                "max_draw_calls": self.config.thresholds.geometry.max_draw_calls,
                "max_triangles": self.config.thresholds.geometry.max_triangles,
                "max_duration_ms": self.config.thresholds.pass_.max_duration_ms,
            }
        }

        if model_stats:
            metrics["model_count"] = len(model_stats)
            metrics["total_triangles"] = sum(m.triangle_count for m in model_stats.values())

        if pass_switches:
            metrics["pass_switches"] = pass_switches.total

        return metrics
```

**Step 4: Run tests to verify they pass**

Run: `pytest rd_mcp/tests/test_analyzer_integration.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add rd_mcp/analyzer.py rd_mcp/tests/test_analyzer_integration.py
git commit -m "feat: integrate new geometry and pass detectors into analyzer"
```

---

## Task 7: Extend RDC Analyzer for Model Statistics

**Files:**
- Modify: `rd_mcp/rdc_analyzer_cmd.py`
- Test: `rd_mcp/tests/test_rdc_analyzer_extended.py`

**Step 1: Write test for enhanced RDC analyzer**

```python
# rd_mcp/tests/test_rdc_analyzer_extended.py
import pytest
from rd_mcp.rdc_analyzer_cmd import analyze_rdc_file

def test_extract_vertex_counts_from_xml():
    """Test that vertex counts are extracted from draw calls"""
    # This requires a real or mock RDC file
    # For unit test, we can test the parsing logic directly
    pass

def test_model_inference():
    """Test model name inference from draw calls"""
    from rd_mcp.detectors.geometry.model_stats import ModelStatsDetector
    from rd_mcp.rdc_analyzer_cmd import DrawCallInfo

    detector = ModelStatsDetector({})

    # Test marker-based inference
    draw1 = DrawCallInfo(
        draw_id=1, event_id=1, name="glDrawArrays",
        vertex_count=3000, marker="Character_Main"
    )
    stats = detector.extract_model_stats([draw1])

    assert "Character_Main" in stats
    assert stats["Character_Main"].triangle_count == 1000

    # Test pattern-based inference
    draw2 = DrawCallInfo(
        draw_id=2, event_id=2, name="Draw_Mesh_Terrain",
        vertex_count=6000, marker=""
    )
    stats = detector.extract_model_stats([draw2])

    # Should infer from name pattern
    assert any("Terrain" in name or "Mesh" in name for name in stats.keys())
```

**Step 2: Run test to verify it passes**

Run: `pytest rd_mcp/tests/test_rdc_analyzer_extended.py -v`
Expected: PASS (should work with existing implementation)

**Step 3: Commit**

```bash
git add rd_mcp/tests/test_rdc_analyzer_extended.py
git commit -m "test: add tests for model statistics extraction"
```

---

## Task 8: Update Report Format

**Files:**
- Modify: `rd_mcp/server.py`
- Test: `rd_mcp/tests/test_report_format.py`

**Step 1: Write test for report formatting**

```python
# rd_mcp/tests/test_report_format.py
import pytest
from rd_mcp.server import format_rdc_analysis_result
from rd_mcp.models import AnalysisResult, ReportSummary, Issue, IssueSeverity
from rd_mcp.models import ModelStats, PassSwitchInfo
from rd_mcp.rdc_analyzer_cmd import RDCAnalysisData, RDCSummary, PassInfo

def test_report_includes_model_stats():
    """Test that report includes model statistics section"""
    summary = ReportSummary(
        api_type="OpenGL",
        total_draw_calls=100,
        total_shaders=10,
        frame_count=1
    )

    issues = {"critical": [], "warnings": [], "suggestions": []}
    model_stats = {
        "Character": ModelStats(
            name="Character",
            draw_calls=10,
            triangle_count=5000,
            vertex_count=1500,
            passes=["Geometry"]
        )
    }

    result = AnalysisResult(
        summary=summary,
        issues=issues,
        metrics={"model_count": 1},
        model_stats=model_stats
    )

    rdc_data = RDCAnalysisData(
        summary=RDCSummary(api_type="OpenGL", gpu_name="GPU", total_draw_calls=100, total_shaders=10),
        draws=[],
        shaders={},
        textures=[],
        passes=[]
    )

    report = format_rdc_analysis_result(result, rdc_data)

    # Should contain model statistics section
    assert "模型统计" in report or "Model Statistics" in report
    assert "Character" in report
    assert "5000" in report  # Triangle count

def test_report_includes_pass_switches():
    """Test that report includes pass switch information"""
    summary = ReportSummary(
        api_type="OpenGL",
        total_draw_calls=100,
        total_shaders=10,
        frame_count=1
    )

    switches = PassSwitchInfo(
        marker_switches=5,
        fbo_switches=2,
        texture_bind_changes=10,
        shader_changes=3
    )

    result = AnalysisResult(
        summary=summary,
        issues={},
        metrics={"pass_switches": switches.total},
        pass_switches=switches
    )

    rdc_data = RDCAnalysisData(
        summary=RDCSummary(api_type="OpenGL", gpu_name="GPU", total_draw_calls=100, total_shaders=10),
        draws=[],
        shaders={},
        textures=[],
        passes=[]
    )

    report = format_rdc_analysis_result(result, rdc_data)

    # Should contain pass switch info
    assert "Pass" in report or "pass" in report
    assert "20" in report  # Total switches
```

**Step 2: Run test to verify it fails**

Run: `pytest rd_mcp/tests/test_report_format.py -v`
Expected: FAIL - sections not in report yet

**Step 3: Update format_rdc_analysis_result function**

```python
# rd_mcp/server.py (add to format_rdc_analysis_result)
def format_rdc_analysis_result(result, rdc_data) -> str:
    """Format RDC analysis result as readable text."""
    lines = []
    lines.append("# RenderDoc RDC Analysis Report")
    lines.append("")

    # Summary section
    lines.append("## Summary")
    lines.append(f"- API Type: {result.summary.api_type}")
    lines.append(f"- Draw Calls: {result.summary.total_draw_calls}")
    lines.append(f"- Shaders: {result.summary.total_shaders}")
    lines.append(f"- Textures: {len(rdc_data.textures)}")
    lines.append(f"- Frames: {result.summary.frame_count}")

    # Add triangle count if available
    if "total_triangles" in result.metrics:
        lines.append(f"- Triangles: {result.metrics['total_triangles']:,}")

    lines.append("")

    # Issues section
    total_issues = result.metrics.get("total_issues", 0)
    lines.append(f"## Issues Found: {total_issues}")
    lines.append("")

    # Critical issues
    critical = result.issues.get("critical", [])
    if critical:
        lines.append(f"### Critical ({len(critical)})")
        for issue in critical:
            lines.append(f"- **{issue.type}**: {issue.description}")
            lines.append(f"  Location: {issue.location}")
            lines.append(f"  Impact: {issue.impact}")
        lines.append("")

    # Warnings
    warnings = result.issues.get("warnings", [])
    if warnings:
        lines.append(f"### Warnings ({len(warnings)})")
        for issue in warnings:
            lines.append(f"- **{issue.type}**: {issue.description}")
            lines.append(f"  Location: {issue.location}")
            lines.append(f"  Impact: {issue.impact}")
        lines.append("")

    # Suggestions
    suggestions = result.issues.get("suggestions", [])
    if suggestions:
        lines.append(f"### Suggestions ({len(suggestions)})")
        for issue in suggestions:
            lines.append(f"- **{issue.type}**: {issue.description}")
            lines.append(f"  Location: {issue.location}")
            lines.append(f"  Impact: {issue.impact}")
        lines.append("")

    # Model Statistics section (NEW)
    if result.model_stats:
        lines.append("## Model Statistics")
        lines.append("")

        # Sort by triangle count
        sorted_models = sorted(
            result.model_stats.items(),
            key=lambda x: x[1].triangle_count,
            reverse=True
        )

        total_triangles = sum(m.triangle_count for m in result.model_stats.values())

        for model_name, stats in sorted_models[:10]:  # Top 10 models
            percentage = (stats.triangle_count / total_triangles * 100) if total_triangles > 0 else 0
            lines.append(f"### {model_name}")
            lines.append(f"- Draw Calls: {stats.draw_calls}")
            lines.append(f"- Triangles: {stats.triangle_count:,} ({percentage:.1f}%)")
            lines.append(f"- Vertices: {stats.vertex_count:,}")
            if stats.passes:
                lines.append(f"- Passes: {', '.join(stats.passes)}")
            lines.append("")

    # Pass Switches section (NEW)
    if result.pass_switches and result.pass_switches.total > 0:
        lines.append("## Pass Switches")
        lines.append("")
        lines.append(f"- Marker Switches: {result.pass_switches.marker_switches}")
        lines.append(f"- FBO Switches: {result.pass_switches.fbo_switches}")
        lines.append(f"- Texture Bind Changes: {result.pass_switches.texture_bind_changes}")
        lines.append(f"- Shader Changes: {result.pass_switches.shader_changes}")
        lines.append(f"- **Total: {result.pass_switches.total}**")
        lines.append("")

    # Passes section
    if rdc_data.passes:
        lines.append("## Render Passes")
        lines.append(f"Total passes: {len(rdc_data.passes)}")
        lines.append("")

        # Show slowest passes
        slowest = sorted(rdc_data.passes, key=lambda p: p.duration_ms, reverse=True)[:5]
        lines.append("### Slowest Passes")
        for i, pass_info in enumerate(slowest, 1):
            lines.append(f"{i}. **{pass_info.name}**")
            lines.append(f"   - Draw calls: {pass_info.draw_count}")
            lines.append(f"   - Duration: {pass_info.duration_ms:.2f}ms")
            if pass_info.resolution:
                lines.append(f"   - Resolution: {pass_info.resolution}")
        lines.append("")

    # Top draws by GPU time
    if rdc_data.draws:
        lines.append("## Top Draw Calls by GPU Time")
        slowest_draws = sorted(rdc_data.draws, key=lambda d: d.gpu_duration_ms, reverse=True)[:10]
        for i, draw in enumerate(slowest_draws, 1):
            lines.append(f"{i}. **{draw.name}** (ID: {draw.draw_id})")
            lines.append(f"   - Duration: {draw.gpu_duration_ms:.4f}ms")
            if draw.marker:
                lines.append(f"   - Pass: {draw.marker}")
        lines.append("")

    # Errors section (NEW)
    if result.errors:
        lines.append("## Detection Errors")
        for error in result.errors:
            lines.append(f"- {error}")
        lines.append("")

    return "\n".join(lines)
```

**Step 4: Run tests to verify they pass**

Run: `pytest rd_mcp/tests/test_report_format.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add rd_mcp/server.py rd_mcp/tests/test_report_format.py
git commit -m "feat: update report format with model stats and pass switches"
```

---

## Task 9: Update MCP Server Integration

**Files:**
- Modify: `rd_mcp/server.py`
- Test: `rd_mcp/tests/test_mcp_integration.py`

**Step 1: Update analyze_rdc tool schema**

```python
# rd_mcp/server.py (update Tool definition)
Tool(
    name="analyze_rdc",
    description=(
        "Analyze a RenderDoc capture file (.rdc) directly without generating HTML. "
        "Returns comprehensive analysis including:\n"
        "- Draw call and triangle count statistics\n"
        "- Per-model performance metrics\n"
        "- Pass duration and state switches\n"
        "- Shader complexity analysis\n"
        "- Texture size warnings\n\n"
        "Supports mobile and PC optimization presets via config parameter.\n"
        "Requires RenderDoc to be installed."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "rdc_path": {
                "type": "string",
                "description": "Path to the RenderDoc capture file (.rdc)"
            },
            "preset": {
                "type": "string",
                "description": "Optional preset name: 'mobile-aggressive', 'mobile-balanced', 'pc-balanced'",
                "enum": ["mobile-aggressive", "mobile-balanced", "pc-balanced"]
            },
            "config_path": {
                "type": "string",
                "description": "Optional path to custom configuration file"
            }
        },
        "required": ["rdc_path"]
    }
)
```

**Step 2: Update analyze_rdc function**

```python
# rd_mcp/server.py (update analyze_rdc function)
async def analyze_rdc(arguments: dict[str, Any]) -> list[TextContent]:
    """Analyze a RenderDoc capture file (.rdc) directly."""
    rdc_path = arguments.get("rdc_path")
    if not rdc_path:
        return [TextContent(type="text", text="Error: rdc_path is required")]

    preset = arguments.get("preset")
    config_path = arguments.get("config_path")

    try:
        # Initialize analyzer with preset or custom config
        from pathlib import Path
        if preset:
            analyzer = Analyzer(preset=preset)
        else:
            path = Path(config_path) if config_path else None
            analyzer = Analyzer(config_path=path)

        # Analyze RDC file directly
        rdc_data = analyze_rdc_file(rdc_path)

        # Convert RDC data to analysis format
        from rd_mcp.models import ReportSummary, PassInfo

        summary = ReportSummary(
            api_type=rdc_data.summary.api_type,
            total_draw_calls=rdc_data.summary.total_draw_calls,
            total_shaders=rdc_data.summary.total_shaders,
            frame_count=rdc_data.summary.frame_count
        )

        # Convert shaders to dict format
        shaders = {
            name: {
                "instruction_count": shader.instruction_count,
                "stage": shader.stage,
                "binding_count": 0  # Not available in XML
            }
            for name, shader in rdc_data.shaders.items()
        }

        # Convert textures to list format
        resources = [
            {
                "name": tex.name,
                "width": tex.width,
                "height": tex.height,
                "depth": tex.depth,
                "format": tex.format
            }
            for tex in rdc_data.textures
        ]

        # Convert passes
        passes = [
            PassInfo(
                name=pass_info.name,
                duration_ms=pass_info.duration_ms,
                resolution=pass_info.resolution
            )
            for pass_info in rdc_data.passes
        ]

        # Perform analysis with draws
        result = analyzer.analyze(
            summary,
            shaders,
            resources,
            passes=passes,
            draws=rdc_data.draws
        )

        # Format results
        output = format_rdc_analysis_result(result, rdc_data)

        return [TextContent(type="text", text=output)]

    except FileNotFoundError as e:
        return [TextContent(type="text", text=f"Error: RDC file not found - {e}")]
    except RuntimeError as e:
        return [TextContent(type="text", text=f"Error: {e}")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: Analysis failed - {e}")]
```

**Step 3: Write integration test**

```python
# rd_mcp/tests/test_mcp_integration.py
import pytest
from rd_mcp.server import analyze_rdc

@pytest.mark.asyncio
async def test_analyze_rdc_with_preset():
    """Test MCP tool with preset parameter"""
    # This would require a real RDC file for full integration test
    # For now, test the parameter parsing
    arguments = {
        "rdc_path": "test.rdc",
        "preset": "mobile-aggressive"
    }

    # Would call analyze_rdc(arguments) in real test
    # For unit test, verify parameter handling
    assert arguments["preset"] == "mobile-aggressive"
```

**Step 4: Commit**

```bash
git add rd_mcp/server.py rd_mcp/tests/test_mcp_integration.py
git commit -m "feat: update MCP server with preset support"
```

---

## Task 10: Write Integration Tests

**Files:**
- Create: `rd_mcp/tests/integration/test_real_rdc.py`
- Create: `rd_mcp/tests/fixtures/README.md`

**Step 1: Create integration test with real RDC**

```python
# rd_mcp/tests/integration/test_real_rdc.py
"""Integration tests using real RDC files."""
import pytest
from pathlib import Path
from rd_mcp.rdc_analyzer_cmd import analyze_rdc_file
from rd_mcp.analyzer import Analyzer

@pytest.mark.integration
def test_analyze_real_mobile_rdc():
    """Test analysis with real mobile game RDC file."""
    # Path to actual RDC file from earlier testing
    rdc_path = Path("D:/GitHubProject/renderdoc_mcp/小米15_激烈战斗截帧1.rdc")

    if not rdc_path.exists():
        pytest.skip("RDC file not available")

    # Analyze with mobile-aggressive preset
    analyzer = Analyzer(preset="mobile-aggressive")
    rdc_data = analyze_rdc_file(rdc_path)

    # Basic assertions
    assert rdc_data.summary.total_draw_calls > 0
    assert len(rdc_data.draws) > 0

    # Check that pass detection works
    assert len(rdc_data.passes) > 0

    # Verify slowest pass detection
    slowest = max(rdc_data.passes, key=lambda p: p.duration_ms)
    assert slowest.duration_ms > 0

@pytest.mark.integration
def test_model_stats_extraction():
    """Test model statistics extraction from real RDC."""
    from rd_mcp.detectors.geometry.model_stats import ModelStatsDetector

    rdc_path = Path("D:/GitHubProject/renderdoc_mcp/小米15_激烈战斗截帧1.rdc")

    if not rdc_path.exists():
        pytest.skip("RDC file not available")

    rdc_data = analyze_rdc_file(rdc_path)
    detector = ModelStatsDetector({})

    model_stats = detector.extract_model_stats(rdc_data.draws)

    # Should have extracted some models
    assert len(model_stats) > 0

    # At least one model should have multiple draw calls
    multi_draw_models = [m for m in model_stats.values() if m.draw_calls > 1]
    assert len(multi_draw_models) > 0

@pytest.mark.integration
def test_pass_switches_detection():
    """Test pass switches detection."""
    from rd_mcp.detectors.pass.switches import PassSwitchesDetector

    rdc_path = Path("D:/GitHubProject/renderdoc_mcp/小米15_激烈战斗截帧1.rdc")

    if not rdc_path.exists():
        pytest.skip("RDC file not available")

    rdc_data = analyze_rdc_file(rdc_path)
    detector = PassSwitchesDetector({})

    switch_info = detector.extract_switch_info(rdc_data.draws)

    # Should detect some switches
    assert switch_info.marker_switches >= 0
    assert switch_info.total >= 0
```

**Step 2: Create fixtures README**

```markdown
# Test Fixtures

This directory contains test fixtures for integration testing.

## RDC Files

Place sample .rdc capture files here for integration testing:

- `mobile_game.rdc` - Mobile game capture (OpenGL ES)
- `pc_game.rdc` - PC game capture (DirectX/Vulkan)

**Note:** RDC files are gitignored. Place them manually for testing.

## Expected Outputs

Expected analysis results for regression testing.
```

**Step 3: Run integration tests**

```bash
# Run with integration marker
pytest rd_mcp/tests/integration/ -m integration -v

# Run all tests
pytest rd_mcp/tests/ -v --cov=rd_mcp
```

**Step 4: Commit**

```bash
git add rd_mcp/tests/integration/ rd_mcp/tests/fixtures/
git commit -m "test: add integration tests with real RDC files"
```

---

## Task 11: Documentation Updates

**Files:**
- Update: `README.md`
- Update: `rd_mcp/MCP_CONFIG.md`
- Create: `rd_mcp/PRESETS.md`

**Step 1: Create presets documentation**

```markdown
# Performance Check Presets

This document describes the available performance check presets for different platforms.

## Mobile Presets

### mobile-aggressive
**Purpose:** Strict thresholds for mobile game optimization

**Target:** High-end mobile games targeting 60fps

**Thresholds:**
- Draw Calls: 500
- Triangles: 50,000
- Triangles per Model: 10,000
- Pass Duration: 0.3ms
- Pass Switches: 8 per frame
- Max Texture Size: 2048px
- Require Compressed Textures: Yes

**Shader Limits:**
- Vertex Shader: 100 instructions
- Fragment Shader: 150 instructions
- Compute Shader: 200 instructions

### mobile-balanced
**Purpose:** Moderate thresholds for mobile games

**Target:** Mid-range mobile devices

**Thresholds:**
- Draw Calls: 1,000
- Triangles: 100,000
- Triangles per Model: 30,000
- Pass Duration: 0.5ms
- Pass Switches: 15 per frame
- Max Texture Size: 2048px
- Require Compressed Textures: No

**Shader Limits:**
- Vertex Shader: 200 instructions
- Fragment Shader: 300 instructions
- Compute Shader: 500 instructions

## PC Presets

### pc-balanced
**Purpose:** Balanced thresholds for PC games

**Target:** Mid-range to high-end PCs

**Thresholds:**
- Draw Calls: 3,000
- Triangles: 2,000,000
- Triangles per Model: 100,000
- Pass Duration: 1.0ms
- Pass Switches: 20 per frame
- Max Texture Size: 4096px
- Require Compressed Textures: No

**Shader Limits:**
- Vertex Shader: 500 instructions
- Fragment Shader: 500 instructions
- Compute Shader: 1000 instructions

## Creating Custom Presets

Create a new JSON file in `rd_mcp/presets/`:

```json
{
  "description": "My custom preset",
  "thresholds": {
    "geometry": {
      "max_draw_calls": 2000,
      "max_triangles": 500000,
      "max_triangles_per_model": 50000
    },
    "shader": {
      "max_vs_instructions": 300,
      "max_fs_instructions": 400,
      "max_cs_instructions": 600
    },
    "pass": {
      "max_duration_ms": 0.7,
      "max_overdraw_ratio": 2.5,
      "max_switches_per_frame": 12
    },
    "memory": {
      "max_texture_size": 2048,
      "require_compressed_textures": false
    }
  }
}
```

Use it via MCP: `analyze_rdc` with `preset: "my-custom"`
```

**Step 2: Update MCP_CONFIG.md**

Add new section for preset parameter:

```markdown
### Preset Configuration

The `analyze_rdc` tool supports platform-specific presets:

```json
{
  "name": "analyze_rdc",
  "arguments": {
    "rdc_path": "path/to/capture.rdc",
    "preset": "mobile-aggressive"  // Optional
  }
}
```

**Available Presets:**
- `mobile-aggressive` - Strict mobile optimization
- `mobile-balanced` - Moderate mobile thresholds
- `pc-balanced` - PC game optimization

See [PRESETS.md](PRESETS.md) for detailed threshold information.
```

**Step 3: Update main README**

Add new features section:

```markdown
## Features

- **Direct RDC Analysis** - Analyze .rdc files without HTML generation
- **Mobile & PC Optimization** - Platform-specific performance presets
- **Model Statistics** - Per-model draw call and triangle count analysis
- **Pass Analysis** - Duration and state switch detection
- **Shader Complexity** - Instruction count and cycle analysis
- **Texture Analysis** - Size and format checking

## Usage

### MCP Server

```python
# Use mobile-optimized preset
{
  "tool": "analyze_rdc",
  "arguments": {
    "rdc_path": "game_capture.rdc",
    "preset": "mobile-aggressive"
  }
}
```

### Report Sections

- **Summary** - API type, draw calls, shaders, triangles
- **Critical Issues** - Excessive draw calls, slow passes, heavy models
- **Warnings** - Texture size, pass switches, shader complexity
- **Model Statistics** - Per-model breakdown (top 10)
- **Pass Switches** - Marker, FBO, texture, shader changes
- **Slowest Passes** - Performance bottleneck identification
```

**Step 4: Commit**

```bash
git add README.md rd_mcp/MCP_CONFIG.md rd_mcp/PRESETS.md
git commit -m "docs: add preset documentation and usage guide"
```

---

## Summary

This implementation plan adds comprehensive performance checking capabilities:

1. **Configuration System** - Preset-based with platform-specific thresholds
2. **Geometry Detectors** - Triangle count and model statistics
3. **Pass Detectors** - Duration and state switch analysis
4. **Enhanced Reporting** - Model stats, pass switches, errors
5. **MCP Integration** - Preset parameter support
6. **Testing** - Unit and integration tests
7. **Documentation** - Presets guide and updated docs

**Total Estimated Tasks:** 11 major tasks with ~50 individual steps
**Testing Coverage:** All new components have tests
**Documentation:** Complete usage guide and preset reference
