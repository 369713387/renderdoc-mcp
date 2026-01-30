# RenderDoc MCP Server - 配置指南

## 快速配置

### 1. 安装依赖

```bash
pip install -r rd_mcp/requirements.txt
```

### 2. 配置 Claude Desktop

**Windows 配置文件位置**: `%APPDATA%\Claude\claude_desktop_config.json`

将以下内容添加到配置文件中：

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

**重要**: 将 `D:\\GitHubProject\\renderdoc_mcp` 替换为你的实际项目路径。

### 3. 重启 Claude Desktop

重启后即可使用 MCP 工具。

## 验证配置

运行测试脚本验证配置是否正确：

```bash
python test_mcp_config.py
```

## 使用示例

```
Can you analyze the RenderDoc report at D:/path/to/report?
```

```
What performance issues did you find in the Vulkan report?
```

```
How many draw calls are in this capture and is it too many?
```

## 故障排除

### 问题: 工具不显示

1. 检查 Python 是否在 PATH 中
2. 验证依赖已安装: `pip list | grep mcp`
3. 检查 Claude Desktop 日志

### 问题: 模块未找到

确保项目路径在配置中正确设置，或者添加 PYTHONPATH:

```json
{
  "mcpServers": {
    "renderdoc": {
      "command": "python",
      "args": ["-m", "rd_mcp.server"],
      "cwd": "D:\\GitHubProject\\renderdoc_mcp",
      "env": {
        "PYTHONPATH": "D:\\GitHubProject\\renderdoc_mcp"
      }
    }
  }
}
```

## 可用工具

| 工具名 | 描述 |
|--------|------|
| `analyze_report` | 全面性能分析，返回所有检测到的问题 |
| `get_summary` | 快速获取报告摘要（API类型、绘制调用数等） |

## 配置选项

编辑 `rd_mcp/config.json` 自定义检测阈值：

```json
{
  "thresholds": {
    "max_draw_calls": 1000,
    "expensive_shader_instructions": 500,
    "large_texture_size": 4096,
    "overdraw_threshold": 2.5
  }
}
```
