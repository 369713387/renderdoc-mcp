# RenderDoc MCP Server Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build an MCP server that analyzes RenderDoc HTML reports and identifies GPU performance issues.

**Architecture:** A standalone MCP server (`rd_mcp/`) that parses RenderDoc's Markdeep HTML reports, applies rule-based performance analysis, and returns structured results via MCP tools.

**Tech Stack:** Python 3.8+, MCP SDK, BeautifulSoup4, lxml, Pydantic, pytest

---

## Task 1: Project Skeleton and Configuration

**Files:**
- Create: `rd_mcp/__init__.py`
- Create: `rd_mcp/config.py`
- Create: `rd_mcp/config.json`
- Create: `rd_mcp/requirements.txt`
- Create: `rd_mcp/README.md`

**Step 1: Create package init file**

```python
# rd_mcp/__init__.py
__version__ = "0.1.0"
```

**Step 2: Create configuration module**

```python
# rd_mcp/config.py
import json
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

DEFAULT_CONFIG_PATH = Path(__file__).parent / "config.json"

@dataclass
class Thresholds:
    max_draw_calls: int = 1000
    expensive_shader_instructions: int = 500
    large_texture_size: int = 4096
    overdraw_threshold: float = 2.5

@dataclass
class OutputConfig:
    include_raw_data: bool = False
    verbose: bool = False

@dataclass
class Config:
    thresholds: Thresholds
    output: OutputConfig

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "Config":
        config_path = path or DEFAULT_CONFIG_PATH
        if not config_path.exists():
            return cls(
                thresholds=Thresholds(),
                output=OutputConfig()
            )

        with open(config_path) as f:
            data = json.load(f)

        return cls(
            thresholds=Thresholds(**data.get("thresholds", {})),
            output=OutputConfig(**data.get("output", {}))
        )
```

**Step 3: Create default config file**

```json
{
  "thresholds": {
    "max_draw_calls": 1000,
    "expensive_shader_instructions": 500,
    "large_texture_size": 4096,
    "overdraw_threshold": 2.5
  },
  "output": {
    "include_raw_data": false,
    "verbose": false
  }
}
```

**Step 4: Create requirements.txt**

```
mcp>=0.1.0
beautifulsoup4>=4.12.0
lxml>=5.0.0
pydantic>=2.0.0
pytest>=7.4.0
pytest-cov>=4.1.0
```

**Step 5: Create README.md**

```markdown
# RenderDoc MCP Server

MCP server for analyzing RenderDoc HTML reports and detecting GPU performance issues.

## Installation

```bash
pip install -e ./rd_mcp
```

## Usage

Configure in Claude Code settings:

```json
{
  "mcpServers": {
    "renderdoc": {
      "command": "python",
      "args": ["-m", "rd_mcp.server"]
    }
  }
}
```

## Available Tools

- `analyze_report`: Full performance analysis
- `get_drawcall_analysis`: Draw call specific issues
- `get_shader_analysis`: Shader performance issues
- `get_resource_analysis`: Resource usage issues
- `get_summary`: Report summary information
```

**Step 6: Commit**

```bash
git add rd_mcp/__init__.py rd_mcp/config.py rd_mcp/config.json rd_mcp/requirements.txt rd_mcp/README.md
git commit -m "feat(mcp): add project skeleton and configuration"
```

---

## Task 2: Data Models

**Files:**
- Create: `rd_mcp/models.py`
- Test: `rd_mcp/tests/test_models.py`

**Step 1: Write the failing test**

```python
# rd_mcp/tests/test_models.py
import pytest
from rd_mcp.models import Issue, IssueSeverity, AnalysisResult, ReportSummary

def test_issue_creation():
    issue = Issue(
        type="excessive_draw_calls",
        severity=IssueSeverity.CRITICAL,
        description="Draw call 数量过多 (1234)，建议合并",
        location="Frame 0"
    )
    assert issue.type == "excessive_draw_calls"
    assert issue.severity == IssueSeverity.CRITICAL

def test_analysis_result_creation():
    result = AnalysisResult(
        summary=ReportSummary(
            api_type="OpenGL",
            total_draw_calls=1234,
            total_shaders=56,
            frame_count=1
        ),
        issues={
            "critical": [
                Issue(
                    type="excessive_draw_calls",
                    severity=IssueSeverity.CRITICAL,
                    description="Draw call 数量过多",
                    location="Frame 0"
                )
            ],
            "warnings": [],
            "suggestions": []
        },
        metrics={
            "draw_call_count": 1234,
            "avg_shader_instructions": 234
        }
    )
    assert len(result.issues["critical"]) == 1
    assert result.summary.total_draw_calls == 1234
```

**Step 2: Run test to verify it fails**

```bash
cd D:/GitHubProject/renderdoc_mcp
pytest rd_mcp/tests/test_models.py -v
```

Expected: `ModuleNotFoundError: No module named 'rd_mcp.models'`

**Step 3: Write minimal implementation**

```python
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
```

**Step 4: Run test to verify it passes**

```bash
pytest rd_mcp/tests/test_models.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add rd_mcp/models.py rd_mcp/tests/test_models.py
git commit -m "feat(mcp): add Pydantic data models"
```

---

## Task 3: HTML Parser - Report Summary Extraction

**Files:**
- Create: `rd_mcp/html_parser.py`
- Modify: `rd_mcp/tests/test_html_parser.py`

**Step 1: Write the failing test**

```python
# rd_mcp/tests/test_html_parser.py
import pytest
from pathlib import Path
from rd_mcp.html_parser import HTMLParser
from rd_mcp.models import ReportSummary

def test_extract_summary_from_valid_html():
    # Create a minimal valid HTML fixture
    html_content = """
    <!DOCTYPE html>
    <html>
    <head><title>Test Report</title></head>
    <body>
        <h1>API: OpenGL</h1>
        <div class="draw-calls">100 draw calls</div>
        <div class="shaders">5 shaders</div>
        <div class="frames">1 frame</div>
    </body>
    </html>
    """
    fixture_path = Path("rd_mcp/tests/fixtures/sample_report.html")
    fixture_path.parent.mkdir(parents=True, exist_ok=True)
    fixture_path.write_text(html_content)

    parser = HTMLParser(str(fixture_path))
    summary = parser.extract_summary()

    assert summary.api_type == "OpenGL"
    assert summary.total_draw_calls == 100
    assert summary.total_shaders == 5
    assert summary.frame_count == 1
```

**Step 2: Run test to verify it fails**

```bash
pytest rd_mcp/tests/test_html_parser.py::test_extract_summary_from_valid_html -v
```

Expected: `ModuleNotFoundError: No module named 'rd_mcp.html_parser'`

**Step 3: Write minimal implementation**

```python
# rd_mcp/html_parser.py
from pathlib import Path
from bs4 import BeautifulSoup
from rd_mcp.models import ReportSummary
import re

class HTMLParser:
    def __init__(self, report_path: str):
        self.report_path = Path(report_path)
        self.soup = None

    def _load_html(self):
        if self.soup is None:
            html_path = self.report_path / "index.html"
            if not html_path.exists():
                raise FileNotFoundError(f"HTML report not found: {html_path}")
            self.soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "lxml")

    def extract_summary(self) -> ReportSummary:
        self._load_html()

        # Extract API type from title or heading
        api_type = "Unknown"
        title = self.soup.find("title")
        if title:
            text = title.get_text()
            for api in ["OpenGL", "Vulkan", "DirectX", "Direct3D", "Metal"]:
                if api in text:
                    api_type = api
                    break

        # Extract metrics - look for common patterns in RenderDoc reports
        body = self.soup.get_text()

        # Try to find draw call count
        draw_match = re.search(r'(\d+)\s*(?:draw calls?|draws?)', body, re.IGNORECASE)
        total_draw_calls = int(draw_match.group(1)) if draw_match else 0

        # Try to find shader count
        shader_match = re.search(r'(\d+)\s*shaders?', body, re.IGNORECASE)
        total_shaders = int(shader_match.group(1)) if shader_match else 0

        # Assume single frame for now
        frame_count = 1

        return ReportSummary(
            api_type=api_type,
            total_draw_calls=total_draw_calls,
            total_shaders=total_shaders,
            frame_count=frame_count
        )
```

**Step 4: Run test to verify it passes**

```bash
pytest rd_mcp/tests/test_html_parser.py::test_extract_summary_from_valid_html -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add rd_mcp/html_parser.py rd_mcp/tests/test_html_parser.py
git commit -m "feat(parser): add HTML parser for report summary extraction"
```

---

## Task 4: Draw Call Detector

**Files:**
- Create: `rd_mcp/detectors/__init__.py`
- Create: `rd_mcp/detectors/drawcall.py`
- Test: `rd_mcp/tests/test_drawcall_detector.py`

**Step 1: Write the failing test**

```python
# rd_mcp/tests/test_drawcall_detector.py
import pytest
from rd_mcp.detectors.drawcall import DrawCallDetector
from rd_mcp.models import Issue, IssueSeverity

def test_detect_excessive_draw_calls():
    detector = DrawCallDetector(threshold={"max_draw_calls": 100})

    issues = detector.detect_excessive_draw_calls(draw_call_count=150)

    assert len(issues) == 1
    assert issues[0].type == "excessive_draw_calls"
    assert issues[0].severity == IssueSeverity.CRITICAL
    assert "150" in issues[0].description

def test_no_issue_when_under_threshold():
    detector = DrawCallDetector(threshold={"max_draw_calls": 1000})

    issues = detector.detect_excessive_draw_calls(draw_call_count=500)

    assert len(issues) == 0
```

**Step 2: Run test to verify it fails**

```bash
pytest rd_mcp/tests/test_drawcall_detector.py -v
```

Expected: `ModuleNotFoundError: No module named 'rd_mcp.detectors'`

**Step 3: Write minimal implementation**

```python
# rd_mcp/detectors/__init__.py
# Empty init file
```

```python
# rd_mcp/detectors/drawcall.py
from rd_mcp.models import Issue, IssueSeverity
from typing import List, Dict

class DrawCallDetector:
    def __init__(self, threshold: Dict):
        self.max_draw_calls = threshold.get("max_draw_calls", 1000)

    def detect_excessive_draw_calls(self, draw_call_count: int) -> List[Issue]:
        if draw_call_count > self.max_draw_calls:
            return [
                Issue(
                    type="excessive_draw_calls",
                    severity=IssueSeverity.CRITICAL,
                    description=f"Draw call 数量过多 ({draw_call_count})，超过阈值 {self.max_draw_calls}，建议合并",
                    location="Frame",
                    impact="high"
                )
            ]
        return []
```

**Step 4: Run test to verify it passes**

```bash
pytest rd_mcp/tests/test_drawcall_detector.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add rd_mcp/detectors/__init__.py rd_mcp/detectors/drawcall.py rd_mcp/tests/test_drawcall_detector.py
git commit -m "feat(detector): add draw call detector"
```

---

## Task 5: Shader Detector

**Files:**
- Create: `rd_mcp/detectors/shader.py`
- Test: `rd_mcp/tests/test_shader_detector.py`

**Step 1: Write the failing test**

```python
# rd_mcp/tests/test_shader_detector.py
import pytest
from rd_mcp.detectors.shader import ShaderDetector
from rd_mcp.models import Issue, IssueSeverity

def test_detect_expensive_shaders():
    detector = ShaderDetector(threshold={"expensive_shader_instructions": 500})

    shaders = {
        "vs_main": {"instructions": 200},
        "ps_main": {"instructions": 600},  # Over threshold
        "cs_compute": {"instructions": 300}
    }

    issues = detector.detect_expensive_shaders(shaders)

    assert len(issues) == 1
    assert issues[0].type == "expensive_shader"
    assert "ps_main" in issues[0].description
    assert "600" in issues[0].description
```

**Step 2: Run test to verify it fails**

```bash
pytest rd_mcp/tests/test_shader_detector.py -v
```

Expected: `ModuleNotFoundError: No module named 'rd_mcp.detectors.shader'`

**Step 3: Write minimal implementation**

```python
# rd_mcp/detectors/shader.py
from rd_mcp.models import Issue, IssueSeverity
from typing import List, Dict, Any

class ShaderDetector:
    def __init__(self, threshold: Dict):
        self.expensive_threshold = threshold.get("expensive_shader_instructions", 500)

    def detect_expensive_shaders(self, shaders: Dict[str, Dict[str, Any]]) -> List[Issue]:
        issues = []
        for shader_name, shader_data in shaders.items():
            instructions = shader_data.get("instructions", 0)
            if instructions > self.expensive_threshold:
                issues.append(
                    Issue(
                        type="expensive_shader",
                        severity=IssueSeverity.WARNING,
                        description=f"着色器 {shader_name} 指令数过高 ({instructions})，超过阈值 {self.expensive_threshold}",
                        location=f"Shader: {shader_name}",
                        impact="medium"
                    )
                )
        return issues
```

**Step 4: Run test to verify it passes**

```bash
pytest rd_mcp/tests/test_shader_detector.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add rd_mcp/detectors/shader.py rd_mcp/tests/test_shader_detector.py
git commit -m "feat(detector): add shader detector"
```

---

## Task 6: Resource Detector

**Files:**
- Create: `rd_mcp/detectors/resource.py`
- Test: `rd_mcp/tests/test_resource_detector.py`

**Step 1: Write the failing test**

```python
# rd_mcp/tests/test_resource_detector.py
import pytest
from rd_mcp.detectors.resource import ResourceDetector
from rd_mcp.models import Issue, IssueSeverity

def test_detect_large_textures():
    detector = ResourceDetector(threshold={"large_texture_size": 4096})

    resources = [
        {"name": "albedo", "width": 1024, "height": 1024},
        {"name": "shadow_map", "width": 4096, "height": 4096},  # At threshold
        {"name": "env_map", "width": 8192, "height": 4096}  # Over threshold
    ]

    issues = detector.detect_large_textures(resources)

    # Should detect env_map (8192 > 4096), shadow_map is at threshold so warning
    assert len(issues) >= 1
    large_texture_issues = [i for i in issues if i.type == "large_texture"]
    assert len(large_texture_issues) >= 1
```

**Step 2: Run test to verify it fails**

```bash
pytest rd_mcp/tests/test_resource_detector.py -v
```

Expected: `ModuleNotFoundError: No module named 'rd_mcp.detectors.resource'`

**Step 3: Write minimal implementation**

```python
# rd_mcp/detectors/resource.py
from rd_mcp.models import Issue, IssueSeverity
from typing import List, Dict, Any

class ResourceDetector:
    def __init__(self, threshold: Dict):
        self.large_texture_size = threshold.get("large_texture_size", 4096)

    def detect_large_textures(self, resources: List[Dict[str, Any]]) -> List[Issue]:
        issues = []
        for resource in resources:
            width = resource.get("width", 0)
            height = resource.get("height", 0)

            # Check if either dimension exceeds threshold
            if width > self.large_texture_size or height > self.large_texture_size:
                issues.append(
                    Issue(
                        type="large_texture",
                        severity=IssueSeverity.WARNING,
                        description=f"纹理 {resource.get('name', 'unknown')} 尺寸过大 ({width}x{height})，考虑使用 mipmap 或降低分辨率",
                        location=f"Resource: {resource.get('name', 'unknown')}",
                        impact="medium"
                    )
                )
        return issues
```

**Step 4: Run test to verify it passes**

```bash
pytest rd_mcp/tests/test_resource_detector.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add rd_mcp/detectors/resource.py rd_mcp/tests/test_resource_detector.py
git commit -m "feat(detector): add resource detector"
```

---

## Task 7: Main Analyzer

**Files:**
- Create: `rd_mcp/analyzer.py`
- Test: `rd_mcp/tests/test_analyzer.py`

**Step 1: Write the failing test**

```python
# rd_mcp/tests/test_analyzer.py
import pytest
from rd_mcp.analyzer import Analyzer
from rd_mcp.models import ReportSummary

def test_analyze_report_with_issues():
    analyzer = Analyzer(config_path=None)  # Use default config

    # Mock data
    summary = ReportSummary(
        api_type="OpenGL",
        total_draw_calls=1500,  # Over default threshold of 1000
        total_shaders=10,
        frame_count=1
    )

    result = analyzer.analyze(summary, shaders={}, resources=[])

    assert result.summary == summary
    assert len(result.issues["critical"]) > 0
    assert any(i.type == "excessive_draw_calls" for i in result.issues["critical"])
```

**Step 2: Run test to verify it fails**

```bash
pytest rd_mcp/tests/test_analyzer.py -v
```

Expected: `ModuleNotFoundError: No module named 'rd_mcp.analyzer'`

**Step 3: Write minimal implementation**

```python
# rd_mcp/analyzer.py
from rd_mcp.config import Config
from rd_mcp.models import ReportSummary, AnalysisResult, Issue, IssueSeverity
from rd_mcp.detectors.drawcall import DrawCallDetector
from rd_mcp.detectors.shader import ShaderDetector
from rd_mcp.detectors.resource import ResourceDetector
from typing import Dict, List, Any

class Analyzer:
    def __init__(self, config_path=None):
        self.config = Config.load(config_path)
        self.drawcall_detector = DrawCallDetector(self.config.thresholds.__dict__)
        self.shader_detector = ShaderDetector(self.config.thresholds.__dict__)
        self.resource_detector = ResourceDetector(self.config.thresholds.__dict__)

    def analyze(
        self,
        summary: ReportSummary,
        shaders: Dict[str, Any],
        resources: List[Dict[str, Any]]
    ) -> AnalysisResult:
        issues = {
            "critical": [],
            "warnings": [],
            "suggestions": []
        }

        # Run detectors
        issues["critical"].extend(
            self.drawcall_detector.detect_excessive_draw_calls(summary.total_draw_calls)
        )

        shader_issues = self.shader_detector.detect_expensive_shaders(shaders)
        for issue in shader_issues:
            issues[issue.severity].append(issue)

        resource_issues = self.resource_detector.detect_large_textures(resources)
        for issue in resource_issues:
            issues[issue.severity].append(issue)

        # Build metrics
        metrics = {
            "draw_call_count": summary.total_draw_calls,
            "shader_count": summary.total_shaders,
            "frame_count": summary.frame_count
        }

        return AnalysisResult(
            summary=summary,
            issues=issues,
            metrics=metrics
        )
```

**Step 4: Run test to verify it passes**

```bash
pytest rd_mcp/tests/test_analyzer.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add rd_mcp/analyzer.py rd_mcp/tests/test_analyzer.py
git commit -m "feat(analyzer): add main analyzer orchestrator"
```

---

## Task 8: MCP Server - Basic Setup

**Files:**
- Create: `rd_mcp/server.py`

**Step 1: Create server stub**

```python
# rd_mcp/server.py
import asyncio
from mcp.server import Server
from mcp.types import Tool, TextContent
from rd_mcp.html_parser import HTMLParser
from rd_mcp.analyzer import Analyzer
from rd_mcp.models import AnalysisResult
import json

app = Server("renderdoc-analysis")

@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="analyze_report",
            description="全面分析 RenderDoc 报告，返回所有性能问题",
            inputSchema={
                "type": "object",
                "properties": {
                    "report_path": {
                        "type": "string",
                        "description": "RenderDoc 报告文件夹路径"
                    }
                },
                "required": ["report_path"]
            }
        ),
        Tool(
            name="get_summary",
            description="获取报告摘要信息（帧数、draw call 数、API 类型等）",
            inputSchema={
                "type": "object",
                "properties": {
                    "report_path": {
                        "type": "string",
                        "description": "RenderDoc 报告文件夹路径"
                    }
                },
                "required": ["report_path"]
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "analyze_report":
        result = await analyze_report_impl(arguments["report_path"])
        return [TextContent(type="text", text=json.dumps(result.dict(), ensure_ascii=False, indent=2))]
    elif name == "get_summary":
        result = await get_summary_impl(arguments["report_path"])
        return [TextContent(type="text", text=json.dumps(result.dict(), ensure_ascii=False, indent=2))]
    else:
        raise ValueError(f"Unknown tool: {name}")

async def analyze_report_impl(report_path: str) -> AnalysisResult:
    parser = HTMLParser(report_path)
    summary = parser.extract_summary()

    analyzer = Analyzer()
    # For now, pass empty shaders/resources - will be extracted in later task
    return analyzer.analyze(summary, shaders={}, resources=[])

async def get_summary_impl(report_path: str):
    parser = HTMLParser(report_path)
    return parser.extract_summary()

async def main():
    from mcp.server.stdio import stdio_server
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )

if __name__ == "__main__":
    asyncio.run(main())
```

**Step 2: Test server starts**

```bash
cd D:/GitHubProject/renderdoc_mcp/rd_mcp
python -c "import server; print('Server module loads successfully')"
```

Expected: No errors

**Step 3: Commit**

```bash
git add rd_mcp/server.py
git commit -m "feat(server): add MCP server with basic tools"
```

---

## Task 9: Integration Test

**Files:**
- Create: `rd_mcp/tests/test_integration.py`

**Step 1: Write integration test**

```python
# rd_mcp/tests/test_integration.py
import pytest
from pathlib import Path
from rd_mcp.html_parser import HTMLParser
from rd_mcp.analyzer import Analyzer

def test_end_to_end_analysis():
    # Create a realistic HTML fixture
    html_content = """
    <!DOCTYPE html>
    <html>
    <head><title>RenderDoc Capture - OpenGL</title></head>
    <body>
        <h1>Frame Capture</h1>
        <p>Total: 1,500 draw calls recorded</p>
        <p>Shaders: 25 shaders used</p>
        <table>
            <tr><td>Draw Call 1</td><td>0.5ms</td></tr>
            <tr><td>Draw Call 2</td><td>0.3ms</td></tr>
        </table>
    </body>
    </html>
    """
    fixture_path = Path("rd_mcp/tests/fixtures/integration_test.html")
    fixture_path.write_text(html_content)

    # Parse
    parser = HTMLParser("rd_mcp/tests/fixtures")
    summary = parser.extract_summary()

    assert summary.api_type == "OpenGL"
    assert summary.total_draw_calls == 1500

    # Analyze
    analyzer = Analyzer()
    result = analyzer.analyze(summary, shaders={}, resources=[])

    # Should detect excessive draw calls
    assert len(result.issues["critical"]) > 0
    assert result.issues["critical"][0].type == "excessive_draw_calls"
```

**Step 2: Run integration test**

```bash
pytest rd_mcp/tests/test_integration.py -v
```

Expected: PASS

**Step 3: Commit**

```bash
git add rd_mcp/tests/test_integration.py
git commit -m "test(integration): add end-to-end integration test"
```

---

## Task 10: Documentation and MCP Configuration

**Files:**
- Create: `rd_mcp/MCP_CONFIG.md`
- Modify: `CLAUDE.md` (update with MCP info)

**Step 1: Create MCP configuration guide**

```markdown
# MCP Configuration Guide

## Claude Code Configuration

Add to your Claude Code settings file:

### Windows
Location: `%APPDATA%\Claude\claude_desktop_config.json`

### macOS/Linux
Location: `~/.config/Claude/claude_desktop_config.json`

## Configuration

```json
{
  "mcpServers": {
    "renderdoc": {
      "command": "python",
      "args": ["-m", "rd_mcp.server"],
      "cwd": "D:/GitHubProject/renderdoc_mcp"
    }
  }
}
```

## Usage

After configuring, restart Claude Code. Then:

```
User: 分析 D:/path/to/report 这个 RenderDoc 报告的性能问题
```

Claude will call the MCP tool and return analysis results.
```

**Step 2: Update CLAUDE.md**

Add section at end:

```markdown
## MCP 服务器集成

项目包含一个 MCP 服务器（`rd_mcp/`），用于在 Claude Code 中分析 RenderDoc 报告。

配置方法见 `rd_mcp/MCP_CONFIG.md`。

可用工具：
- `analyze_report`: 全面分析性能问题
- `get_summary`: 获取报告摘要
- `get_drawcall_analysis`: Draw Call 分析
- `get_shader_analysis`: 着色器分析
- `get_resource_analysis`: 资源分析
```

**Step 3: Commit**

```bash
git add rd_mcp/MCP_CONFIG.md CLAUDE.md
git commit -m "docs(mcp): add MCP configuration guide and update CLAUDE.md"
```

---

## Task 11: Final Verification

**Step 1: Run all tests**

```bash
cd D:/GitHubProject/renderdoc_mcp
pytest rd_mcp/tests/ -v --cov=rd_mcp
```

Expected: All tests pass, coverage > 80%

**Step 2: Verify MCP server can be imported**

```bash
python -c "from rd_mcp.server import app; print('MCP server loaded successfully')"
```

Expected: No errors

**Step 3: Check package can be installed**

```bash
pip install -e ./rd_mcp
```

Expected: Successful installation

**Step 4: Final documentation review**

Ensure all documentation is complete and consistent.

**Step 5: Final commit**

```bash
git add .
git commit -m "feat(mcp): complete RenderDoc MCP server implementation"
```

---

## Notes for Implementation

1. **TDD Approach**: Always write the test first, verify it fails, then implement.

2. **YAGNI Principle**: Only implement what's needed for the current task. Don't add "nice to have" features.

3. **Frequent Commits**: Commit after each completed task.

4. **HTML Parsing**: The current HTML parser uses basic regex/pattern matching. For production, you may need to adjust based on actual RenderDoc HTML structure.

5. **Extensibility**: The detector pattern makes it easy to add new analysis rules later.

6. **Configuration**: All thresholds are configurable via `config.json`.

7. **Error Handling**: Add proper error handling as you encounter edge cases during testing.
