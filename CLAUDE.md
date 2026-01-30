# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 在此代码库中工作时提供指导。

## 项目概述

这是一个 RenderDoc Python 脚本（`rd.py`），用于从 RenderDoc 捕获文件（.rdc）生成全面的 HTML 报告。它分析 GPU 捕获，提取 API 调用、着色器、资源和性能指标，然后使用 Markdeep 和 Mermaid 图表生成交互式可视化。

## 运行脚本

### 在 RenderDoc 中运行（主要方法）
1. 启动 RenderDoc 并打开一个 .rdc 捕获文件
2. 打开 `Window -> Python Shell`
3. 点击 `Run Scripts -> Open` 并选择 `rd.py`
4. 点击 `Run` 生成报告

### 独立运行（命令行）
```bash
python rd.py <path/to/capture.rdc>
```

此方式需要 RenderDoc Python API 在 Python 路径中可用。

## 配置

配置存储在 Windows 的 `%APPDATA%/rd.json` 中。如果文件不存在，脚本将使用默认值创建该文件。主要选项：

- `MINIMALIST`: 如果为 True，仅生成摘要报告
- `WRITE_MALIOC`、`WRITE_CONST_BUFFER`、`WRITE_PIPELINE` 等：切换各种导出选项
- `WRITE_PSO_DAG`: 生成管线状态对象（PSO）DAG 图
- `WRITE_ALL_DRAWS`: 在详细输出中包含所有绘制调用

## 架构

### 主要入口点
- `rdc_main(controller)` (rd.py:3454): 主分析流程编排
- `setup_rdc(filename)` (rd.py:3147): 初始化 RenderDoc 捕获和回放控制器
- `shutdown_rdc(cap, controller)` (rd.py:3492): 清理 RenderDoc 资源

### 分析流程

脚本按顺序执行四个阶段的流程：

1. **`fetch_gpu_counters(controller)`** - 收集 GPU 性能指标（绘制持续时间等）
2. **`generate_raw_data(controller)`** - 通过 `visit_action()` 遍历捕获的动作树，提取绘制调用、API 调用、着色器和资源
3. **`generate_derived_data(controller)`** - 处理原始数据以进行更高级别的分析
4. **`generate_viz(controller)`** - 使用 Markdeep 语法编写 HTML 报告

### 全局状态管理

脚本使用大量全局变量：
- `g_assets_folder`: 报告的输出目录
- `g_frame`: 帧分析数据结构
- `g_draw_durations`: GPU 计时数据
- `api_full_log`、`api_short_log`: API 调用日志文件
- `API_TYPE`: 图形 API 类型（OpenGL、DirectX、Vulkan 等）

### 动作树遍历

核心分析发生在 `visit_action()` 中（搜索此函数），它递归处理 RenderDoc 的动作树结构。每个动作代表一个绘制调用、计算调度或标记区域。

### 报告生成

- 使用 **Markdeep** 生成自包含的 HTML（Markdown + 嵌入式 CSS/JS）
- 使用 **Mermaid** 生成流程图和 DAG
- 静态 Web 资源位于 `src/` 文件夹（markdeep.min.js、lazysizes.js、rdc.js、CSS）

## 主要枚举

- `ShaderStage`: VS、HS、DS、GS、PS、CS（着色器管线阶段）
- `GLChunk`: OpenGL API 调用的广泛枚举（rd.py:80-900+）

## 依赖项

- **renderdoc**: RenderDoc Python API (https://renderdoc.org/docs/python_api/index.html)
- 标准库: `pathlib`、`json`、`struct`、`pprint`、`collections`、`enum`

## 可选集成

- **FBX SDK**: 用于 3D 模型处理（`fbx-tools/` 文件夹）
- **Intel GPA**: 用于 GPU 性能计数器集成（`intel-gpa-plugin/` 文件夹）

## 路径处理

脚本使用 pathlib 中 Windows 特定的 `WindowsPath`，期望使用 Windows 风格的路径。输出文件夹在输入 .rdc 文件旁边创建。

## MCP Server Integration

### 概述

`rd_mcp/` 目录包含一个 Model Context Protocol (MCP) 服务器，使 AI 助手能够分析 RenderDoc HTML 报告并提供性能洞察。

### 架构

```
rd_mcp/
├── server.py              # MCP 服务器主入口
├── analyzer.py            # 主分析器，协调所有检测器
├── html_parser.py         # HTML 报告解析器
├── config.py              # 配置管理
├── models.py              # Pydantic 数据模型
├── detectors/             # 性能问题检测器
│   ├── drawcall.py        # 绘制调用检测器
│   ├── shader.py          # 着色器检测器
│   └── resource.py        # 资源检测器
├── tests/                 # 测试套件
│   ├── test_integration.py    # 集成测试
│   ├── test_analyzer.py       # 分析器测试
│   ├── test_html_parser.py    # 解析器测试
│   └── test_*.py              # 单元测试
├── MCP_CONFIG.md         # MCP 配置指南
└── requirements.txt       # Python 依赖
```

### MCP 工具

服务器提供两个工具：

1. **analyze_report**: 对 RenderDoc HTML 报告执行全面分析
   - 检测过多的绘制调用
   - 识别昂贵的着色器
   - 发现大纹理
   - 返回分类的问题（严重、警告、建议）

2. **get_summary**: 提取报告摘要信息
   - API 类型
   - 绘制调用数量
   - 着色器数量
   - 帧数

### 使用示例

```
用户: 分析位于 D:/game/captures/scene1 的 RenderDoc 报告

Claude: 我将为您分析 RenderDoc 报告。

[分析结果]
# RenderDoc 分析报告

## 摘要
- API 类型: Vulkan
- 绘制调用: 2847
- 着色器: 42
- 帧: 1

## 发现的问题: 4

### 严重 (1)
- **excessive_draw_calls**: Draw call 数量过多 (2847)，超过阈值 1000，建议合并
  位置: Frame
  影响: high

### 警告 (3)
- **expensive_shader**: 着色器 ps_complex 指令数过高 (1200)，超过阈值 500
  位置: Shader: ps_complex
  影响: medium
[...]
```

### 配置 Claude Desktop

编辑 Claude Desktop 配置文件：

- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Linux:** `~/.config/Claude/claude_desktop_config.json`

添加：

```json
{
  "mcpServers": {
    "renderdoc": {
      "command": "python",
      "args": ["-m", "rd_mcp.server"],
      "env": {
        "PYTHONPATH": "D:\\GitHubProject\\renderdoc_mcp"
      }
    }
  }
}
```

详细配置说明请参阅 `rd_mcp/MCP_CONFIG.md`。

### 测试

运行测试套件：

```bash
pytest rd_mcp/tests/ -v --cov=rd_mcp
```

### 开发

- **TDD 方法**: 所有组件都先编写测试
- **类型安全**: 使用 Pydantic 模型进行数据验证
- **错误处理**: 全面的文件操作和解析错误处理
- **文档**: 每个模块都有详细的文档字符串

### 关键组件

- **HTMLParser**: 解析 RenderDoc HTML 报告，提取摘要信息
- **Analyzer**: 编排所有检测器进行综合分析
- **DrawCallDetector**: 检测过多的绘制调用
- **ShaderDetector**: 识别指令数过高的着色器
- **ResourceDetector**: 发现过大的纹理资源
