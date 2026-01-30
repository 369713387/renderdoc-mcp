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
