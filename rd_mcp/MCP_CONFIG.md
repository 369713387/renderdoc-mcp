# RenderDoc MCP Server Configuration

This document provides configuration instructions for the RenderDoc MCP (Model Context Protocol) server.

## Overview

The RenderDoc MCP server enables AI assistants to analyze RenderDoc graphics debugging capture reports and provide performance insights. It integrates with Claude Desktop and other MCP-compatible clients.

## Installation

### Prerequisites

- Python 3.11 or higher
- RenderDoc capture reports (HTML format)
- MCP-compatible client (e.g., Claude Desktop)

### Setup

1. **Install dependencies:**

```bash
pip install -r requirements.txt
```

2. **Configure Claude Desktop:**

Edit the Claude Desktop configuration file:

- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Linux:** `~/.config/Claude/claude_desktop_config.json`

Add the RenderDoc MCP server configuration:

```json
{
  "mcpServers": {
    "renderdoc": {
      "command": "python",
      "args": [
        "-m",
        "rd_mcp.server"
      ],
      "env": {
        "PYTHONPATH": "/path/to/renderdoc_mcp"
      }
    }
  }
}
```

Replace `/path/to/renderdoc_mcp` with the absolute path to your `renderdoc_mcp` directory.

**On Windows, use:**

```json
{
  "mcpServers": {
    "renderdoc": {
      "command": "python",
      "args": [
        "-m",
        "rd_mcp.server"
      ],
      "env": {
        "PYTHONPATH": "D:\\GitHubProject\\renderdoc_mcp"
      }
    }
  }
}
```

3. **Restart Claude Desktop** to load the server.

## Usage

### Available Tools

Once configured, the server provides two tools:

#### 1. `analyze_report`

Performs comprehensive analysis of a RenderDoc HTML report.

**Parameters:**
- `report_path` (required): Path to the RenderDoc HTML report directory
- `config_path` (optional): Path to custom configuration file
- `preset` (optional): Preset name to use (e.g., 'mobile-aggressive', 'mobile-balanced', 'pc-balanced')

**Example usage in Claude:**

```
Please analyze the RenderDoc report at D:/projects/my_game/capture/report
```

```
Please analyze the RenderDoc report at D:/projects/my_game/capture/report using mobile-aggressive preset
```

```
Please analyze the RenderDoc report at D:/projects/my_game/capture/report using preset pc-balanced
```

**Returns:**
- Summary information (API type, draw calls, shaders, frames)
- Detected issues categorized by severity (critical, warnings, suggestions)
- Analysis metrics

#### 2. `get_summary`

Extracts summary information without full analysis.

**Parameters:**
- `report_path` (required): Path to the RenderDoc HTML report directory

**Example usage in Claude:**

```
Get a summary of the RenderDoc report at D:/projects/my_game/capture/report
```

**Returns:**
- Basic metrics (API type, draw calls, shaders, frames)

## Configuration

### Default Thresholds

The server uses default thresholds for detecting issues:

- **Max Draw Calls:** 1000 (critical if exceeded)
- **Expensive Shader Instructions:** 500 (warning if exceeded)
- **Large Texture Size:** 4096 pixels (warning if exceeded)

### Custom Configuration

Create a custom `config.json` file to adjust thresholds:

```json
{
  "thresholds": {
    "max_draw_calls": 500,
    "expensive_shader_instructions": 300,
    "large_texture_size": 2048,
    "overdraw_threshold": 2.0
  },
  "output": {
    "include_raw_data": false,
    "verbose": true
  }
}
```

Reference your custom config when analyzing:

```
Analyze the report at D:/capture/report using config at D:/custom_config.json
```

## Preset Configurations

The server includes predefined presets optimized for different development scenarios:

### Available Presets

1. **mobile-aggressive**: Strict thresholds for mobile optimization
   - Max draw calls: 500
   - Max shader instructions: 100-200
   - Max texture size: 2048px
   - Strict pass duration: 0.3ms

2. **mobile-balanced**: Balanced thresholds for mid-range mobile devices
   - Max draw calls: 1000
   - Max shader instructions: 300-600
   - Max texture size: 2048px
   - Moderate pass duration: 0.5ms

3. **pc-balanced**: Balanced thresholds for desktop gaming
   - Max draw calls: 2000
   - Max shader instructions: 500-1000
   - Max texture size: 4096px
   - Standard pass duration: 1.0ms

### Using Presets

Presets can be used instead of or in combination with custom configurations:

```
# Use a preset directly
Analyze the report at D:/capture/report using mobile-aggressive preset

# Use preset with custom overrides
Analyze the report at D:/capture/report using pc-balanced preset with additional overrides
```

### Preset Priority Order

1. Preset (highest priority)
2. Custom config file
3. Default configuration (lowest priority)

If multiple configuration sources are provided, presets take precedence over config files, and both take precedence over defaults.

## RenderDoc Report Format

The server expects RenderDoc HTML reports with the following structure:

```
report_directory/
├── index.html       # Main HTML report
└── [other files]
```

The HTML report should contain:
- Title or heading with API type (OpenGL, Vulkan, DirectX, Metal)
- Draw call count (e.g., "1250 draw calls")
- Shader count (e.g., "15 shaders")

## Example Session

```
User: Analyze my RenderDoc capture at D:/game/captures/scene1

Claude: I'll analyze the RenderDoc report for you.

[Analysis Result]
# RenderDoc Analysis Report

## Summary
- API Type: Vulkan
- Draw Calls: 2847
- Shaders: 42
- Frames: 1

## Issues Found: 4

### Critical (1)
- **excessive_draw_calls**: Draw call 数量过多 (2847)，超过阈值 1000，建议合并
  Location: Frame
  Impact: high

### Warnings (3)
- **expensive_shader**: 着色器 ps_complex 指令数过高 (1200)，超过阈值 500
  Location: Shader: ps_complex
  Impact: medium
[...]
```

## Troubleshooting

### Server Not Starting

1. **Check Python path:** Ensure Python is in your system PATH
2. **Verify PYTHONPATH:** Make sure it points to the correct directory
3. **Check dependencies:** Run `pip list | grep mcp` to verify MCP is installed

### Analysis Errors

1. **Report not found:** Ensure the `report_path` points to a directory containing `index.html`
2. **Invalid report:** Check that the HTML file is valid UTF-8 encoded
3. **No data extracted:** Verify the HTML contains draw call and shader information

### Claude Desktop Configuration

1. **Config file location:** Check you're editing the correct config file for your OS
2. **JSON syntax:** Validate JSON syntax using a linter
3. **Restart required:** Claude Desktop must be restarted after config changes

## Development

### Running the Server Directly

For testing, you can run the server directly:

```bash
python -m rd_mcp.server
```

### Testing

Run the test suite:

```bash
pytest rd_mcp/tests/ -v --cov=rd_mcp
```

## License

This project is licensed under the MIT License.
