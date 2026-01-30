# RenderDoc MCP Server

MCP server for analyzing RenderDoc HTML reports and detecting GPU performance issues.

## Features

- **Automated Performance Analysis**: Detects common GPU performance issues
  - Excessive draw calls
  - Expensive shaders (high instruction count)
  - Large textures (memory optimization opportunities)

- **Integration with AI**: Works seamlessly with Claude Desktop for intelligent analysis

- **Flexible Configuration**: Customizable thresholds for different use cases

## Installation

### From Source

```bash
# Install dependencies
pip install -r rd_mcp/requirements.txt

# Or install with pip (editable mode)
pip install -e .
```

## MCP Server Configuration

### Step 1: Locate Claude Desktop Config

**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Linux**: `~/.config/Claude/claude_desktop_config.json`

### Step 2: Add MCP Server

Add the following to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "renderdoc": {
      "command": "python",
      "args": ["-m", "rd_mcp.server"],
      "cwd": "D:\\GitHubProject\\renderdoc_mcp"
    }
  }
}
```

**Update the path** `D:\\GitHubProject\\renderdoc_mcp` to your actual project location.

### Step 3: Restart Claude Desktop

Restart Claude Desktop to load the new MCP server.

## Usage Examples

### Basic Analysis

```
Can you analyze the RenderDoc report at D:/renders/ue4_capture?
```

### Specific Questions

```
What performance issues did you find in the Vulkan report?
```

```
How many draw calls are in this capture and is it too many?
```

## Available Tools

- **`analyze_report`**: Full performance analysis with all detectors
  - Returns issues categorized by severity (critical, warning, suggestion)
  - Includes metrics and recommendations

- **`get_summary`**: Quick report summary
  - API type (OpenGL, Vulkan, DirectX, Metal)
  - Total draw calls
  - Shader count
  - Frame count

## Configuration

Edit `rd_mcp/config.json` to customize detection thresholds:

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

## Running the Server Directly

For testing or development, you can run the server directly:

```bash
python -m rd_mcp.server
```

The server uses stdio for MCP communication and will wait for commands.
