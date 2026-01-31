# render-doctor

## Core Features

### RenderDoc HTML Report Generation
The main script `rd.py` generates comprehensive HTML reports from RenderDoc capture files (.rdc). It provides detailed analysis of GPU performance including API calls, shaders, resources, and visualizations.

### MCP Server Integration
The `rd_mcp/` directory contains a Model Context Protocol (MCP) server that enables AI assistants to analyze RenderDoc reports and provide performance insights.

## How to use?

### Basic Usage
- Fork this repository `render-doctotor`.
- Launch RenderDoc, open a rdc capture file.
- Click `Interactive Python Shell` (you might need to activate this window from `Menu - Window - Python Shell`).
- Click `Run Scripts` and `Open`, select `render-doctotor/rd.py` from this repository.
- Click `Run` and you will get a report folder named as your rdc capture file.

### MCP Server for AI Analysis
Configure the MCP server in Claude Desktop to get AI-powered performance analysis:

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

Then use commands like:
- "Analyze my RenderDoc capture at D:/game/captures/scene1"
- "Get a summary of the RenderDoc report using mobile-aggressive preset"
- "What performance issues do you find in this capture?"

## 如何使用？

- Fork 本仓库 `render-doctotor`。
- 启动 RenderDoc，载入一个 rdc 文件。
- 点击 `Interactive Python Shell` （如果你从未使用过这个功能，需要点击 `菜单 - Window - Python Shell` 激活它）。
- 点击 `Run Scripts` 以及 `Open`, 选择 `render-doctotor/rd.py`。
- 点击 `Run`，运气好的话你会得到一个与 rdc 文件同名的报告文件夹。

## New Features (Enhanced Analysis)

### 1. Performance Presets
The MCP server includes three optimized presets for different development scenarios:

- **mobile-aggressive**: Strict thresholds for mobile optimization
  - Max 500 draw calls
  - Max 100-200 shader instructions
  - Max 2048px texture size
  - Strict 0.3ms pass duration

- **mobile-balanced**: Balanced thresholds for mid-range mobile devices
  - Max 1000 draw calls
  - Max 300-600 shader instructions
  - Max 2048px texture size
  - Moderate 0.5ms pass duration

- **pc-balanced**: Balanced thresholds for desktop gaming
  - Max 2000 draw calls
  - Max 500-1000 shader instructions
  - Max 4096px texture size
  - Standard 1.0ms pass duration

### 2. Advanced Performance Analysis
Enhanced detection capabilities include:

- **Model Statistics**: Detailed triangle count analysis per model
- **Render Pass Analysis**: Duration and switch detection
- **Geometry Optimization**: Triangle count and draw call optimization
- **Shader Performance**: Instruction count analysis for all shader stages
- **Memory Management**: Texture size and compression detection
- **Overdraw Analysis**: Pixel overdraw ratio measurement

### 3. Custom Configuration
Flexible configuration options:

```json
{
  "preset": "mobile-balanced",
  "thresholds": {
    "geometry": {
      "max_draw_calls": 1500,
      "max_triangles": 300000
    },
    "shader": {
      "max_vs_instructions": 400
    }
  }
}
```

### 4. Multi-Platform Support
Optimized for various graphics APIs:
- OpenGL
- Vulkan
- DirectX 11/12
- Metal

### 5. Comprehensive Reporting
- Performance metrics with severity classification
- Optimized suggestions for common bottlenecks
- Visualizations using Markdeep and Mermaid
- Detailed shader and resource analysis

## Sample Reports

- [UE4's Third Person sample](https://www.vinjn.com/rd-samples/ue4-third-person-2021-04-11/)
- [Unity's default URP sample](https://www.vinjn.com/rd-samples/urp-test-gles/)

## Implementataion details

### renderdoc python api
https://renderdoc.org/docs/python_api/renderdoc/index.html

### markdeep
https://casual-effects.com/markdeep/features.md.html

### mermaid
https://mermaid-js.github.io/mermaid/#/flowchart?id=flowcharts-basic-syntax


## Documentation

For detailed documentation, refer to:

- **[MCP Configuration Guide](rd_mcp/MCP_CONFIG.md)** - Complete setup and configuration instructions
- **[Preset Documentation](rd_mcp/PRESETS.md)** - Available presets and usage examples
- **[RenderDoc Python API](https://renderdoc.org/docs/python_api/renderdoc/index.html)** - Official RenderDoc documentation
- **[Markdeep Features](https://casual-effects.com/markdeep/features.md.html)** - Report generation capabilities
- **[Mermaid Charts](https://mermaid-js.github.io/mermaid/#/flowchart?id=flowcharts-basic-syntax)** - Visualization documentation

## FBX Python SDK
https://www.autodesk.com/developer-network/platform-technologies/fbx-sdk-2020-2-1