# RenderDoc AI 性能分析设计文档

**日期**: 2025-01-30
**状态**: 设计阶段

## 概述

创建一个 MCP (Model Context Protocol) 服务器，当用户在 Claude Code 中打开 RenderDoc 生成的 HTML 报告时，可以调用 MCP 工具对报告进行 AI 性能分析，识别 Draw Call 优化、着色器性能、资源使用等方面的潜在问题。

## 架构

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Claude Code    │────▶│  MCP 服务器      │────▶│  HTML 报告解析   │
│  (用户界面)     │     │  (rd_mcp)        │     │  模块           │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                │
                                ▼
                         ┌──────────────────┐
                         │  性能隐患检测     │
                         │  (规则引擎)       │
                         └──────────────────┘
                                │
                                ▼
                         ┌──────────────────┐
                         │  结构化分析结果   │
                         │  返回给 Claude    │
                         └──────────────────┘
```

## 组件设计

### 1. MCP 服务器入口 (`server.py`)

```python
class RenderDocAnalysisServer:
    """MCP 服务器，提供性能分析工具"""

    # 提供的工具
    - analyze_report(report_path: str) -> AnalysisResult
    - get_drawcall_summary(report_path: str) -> Summary
    - detect_overdraw(report_path: str) -> OverdrawIssues
    - analyze_shaders(report_path: str) -> ShaderIssues
    - analyze_resources(report_path: str) -> ResourceIssues
```

### 2. HTML 报告解析器 (`html_parser.py`)

负责从 RenderDoc 生成的 HTML 报告中提取性能数据：

- 解析 Markdeep 生成的 HTML 结构
- 提取绘制调用列表和 GPU 计时数据
- 提取着色器信息（指令数、寄存器使用）
- 提取纹理/缓冲资源信息
- 提取 API 调用日志

### 3. 性能分析引擎 (`analyzer.py`)

基于规则的性能问题检测：

- **Draw Call 分析**：检测过多 draw call、相似的 draw call（可合并）、空 draw call
- **着色器分析**：高指令数着色器、复杂数学运算、过度分支
- **资源分析**：过大纹理、低效纹理格式、冗余资源绑定
- **管线状态**：频繁的状态切换、冗余绑定

### 4. 检测器模块 (`detectors/`)

- `drawcall.py` - Draw Call 相关问题检测
- `shader.py` - 着色器性能分析
- `resource.py` - 资源使用分析
- `pipeline.py` - 管线状态变更分析

## 文件结构

```
renderdoc_mcp/
├── rd.py                          # 现有脚本（不变）
├── rd_mcp/                        # MCP 服务器独立目录
│   ├── server.py                  # MCP 服务器入口
│   ├── html_parser.py             # HTML 报告解析
│   ├── analyzer.py                # 性能问题检测引擎
│   ├── detectors/
│   │   ├── __init__.py
│   │   ├── drawcall.py           # Draw Call 分析
│   │   ├── shader.py             # 着色器分析
│   │   ├── resource.py           # 资源分析
│   │   └── pipeline.py           # 管线状态分析
│   ├── models.py                  # 数据模型定义
│   ├── config.py                  # 配置管理
│   ├── config.json               # 默认配置文件
│   ├── requirements.txt          # Python 依赖
│   ├── README.md                 # MCP 使用说明
│   └── tests/                    # 测试目录
│       ├── fixtures/
│       │   └── sample_reports/   # 示例 HTML 报告
│       ├── test_html_parser.py
│       ├── test_detectors.py
│       └── test_integration.py
└── docs/
    └── 2025-01-30-ai-performance-analysis.md
```

## 数据流

```
HTML 报告
    │
    ▼
┌─────────────────────────────────────────┐
│ HTMLParser.extract_data()               │
│ - 读取 index.html                       │
│ - 解析 Markdeep 结构                    │
│ - 提取性能数据表、着色器列表、资源列表   │
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│ StructuredData                          │
│ {                                       │
│   "draw_calls": [...],                  │
│   "shaders": {...},                     │
│   "resources": [...],                   │
│   "gpu_timings": {...}                  │
│ }                                       │
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│ Analyzer.detect_issues()                │
│ - 应用性能规则                          │
│ - 识别异常模式                          │
│ - 生成问题列表                          │
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│ AnalysisResult                          │
│ {                                       │
│   "critical_issues": [...],             │
│   "warnings": [...],                    │
│   "suggestions": [...],                 │
│   "metrics": {...}                      │
│ }                                       │
└─────────────────────────────────────────┘
    │
    ▼
MCP 返回给 Claude → 用户可见
```

## MCP 工具接口

### 可用工具

| 工具名 | 描述 |
|--------|------|
| `analyze_report` | 全面分析 RenderDoc 报告，返回所有性能问题 |
| `get_drawcall_analysis` | 专门分析 Draw Call 相关问题 |
| `get_shader_analysis` | 专门分析着色器性能问题 |
| `get_resource_analysis` | 专门分析资源使用问题（纹理、缓冲） |
| `get_summary` | 获取报告摘要信息 |

### 返回数据格式

```json
{
  "summary": {
    "api_type": "OpenGL/Vulkan/DirectX",
    "total_draw_calls": 1234,
    "total_shaders": 56,
    "frame_count": 1
  },
  "issues": {
    "critical": [
      {
        "type": "excessive_draw_calls",
        "description": "Draw call 数量过多 (1234)，建议合并",
        "location": "Frame 0",
        "impact": "high"
      }
    ],
    "warnings": [],
    "suggestions": []
  },
  "metrics": {
    "draw_call_count": 1234,
    "avg_shader_instructions": 234,
    "large_texture_count": 5
  }
}
```

## 用户使用流程

```
1. 用户运行 rd.py 生成 HTML 报告
   └─> 生成 report_folder/index.html

2. 用户在 Claude Code 中请求分析
   用户: "分析 D:\path\to\report 这个 RenderDoc 报告的性能问题"

3. Claude 调用 MCP 工具
   └─> mcp_server.analyze_report("D:\\path\\to\\report")

4. MCP 返回结构化结果
   └─> Claude 用自然语言总结给用户

5. 用户可以追问
   用户: "详细分析着色器性能"
   └─> mcp_server.analyze_shaders(...)
```

## 配置

**rd_mcp/config.json**：
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

## 错误处理

| 场景 | 处理方式 |
|------|----------|
| HTML 解析失败 | 报告支持的报告格式，建议用户使用兼容的 rd.py 版本 |
| 文件不存在 | 提供清晰的路径错误信息 |
| 数据缺失 | 跳过缺失的分析模块，返回已完成的部分结果 |
| 报告过大 | 分段分析或只分析摘要 |

## 依赖项

- `mcp`: MCP 服务器框架
- `beautifulsoup4`: HTML 解析
- `lxml`: HTML/XML 解析器
- `pydantic`: 数据验证

## 测试策略

1. 使用 rd.py 生成示例报告作为测试夹具
2. 单元测试：验证解析器能正确提取数据
3. 规则测试：验证检测器能识别预期的问题
4. 集成测试：端到端验证 MCP 工具返回正确结果
