# rd_mcp/server.py
"""MCP server for RenderDoc analysis.

This module provides a Model Context Protocol server that enables
AI assistants to analyze RenderDoc capture reports and provide
performance insights.
"""
import asyncio
import json
from pathlib import Path
from typing import Any, Optional

from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions, Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
)

from rd_mcp.html_parser import HTMLParser
from rd_mcp.analyzer import Analyzer
from rd_mcp.models import ReportSummary


# Create MCP server instance
server = Server("renderdoc-analyzer")

# Global analyzer instance (reused across calls)
_analyzer: Optional[Analyzer] = None


def get_analyzer() -> Analyzer:
    """Get or create the global analyzer instance."""
    global _analyzer
    if _analyzer is None:
        _analyzer = Analyzer()
    return _analyzer


@server.list_resources()
async def handle_list_resources() -> list[str]:
    """List available resources."""
    return [
        "renderdoc://reports",
        "renderdoc://config"
    ]


@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="analyze_report",
            description=(
                "Perform a comprehensive analysis of a RenderDoc HTML report. "
                "Detects performance issues including excessive draw calls, "
                "expensive shaders, and large textures. Returns a detailed "
                "analysis with issues categorized by severity."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "report_path": {
                        "type": "string",
                        "description": "Path to the RenderDoc HTML report directory (containing index.html)"
                    },
                    "config_path": {
                        "type": "string",
                        "description": "Optional path to custom configuration file"
                    }
                },
                "required": ["report_path"]
            }
        ),
        Tool(
            name="get_summary",
            description=(
                "Extract summary information from a RenderDoc HTML report. "
                "Returns basic metrics like API type, draw call count, "
                "shader count, and frame count without performing analysis."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "report_path": {
                        "type": "string",
                        "description": "Path to the RenderDoc HTML report directory (containing index.html)"
                    }
                },
                "required": ["report_path"]
            }
        )
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent | ImageContent | EmbeddedResource]:
    """Handle tool calls."""
    if name == "analyze_report":
        return await analyze_report(arguments)
    elif name == "get_summary":
        return await get_summary(arguments)
    else:
        raise ValueError(f"Unknown tool: {name}")


async def analyze_report(arguments: dict[str, Any]) -> list[TextContent]:
    """Analyze a RenderDoc report and return comprehensive results.

    Args:
        arguments: Tool arguments containing report_path and optional config_path

    Returns:
        TextContent containing analysis results
    """
    report_path = arguments.get("report_path")
    if not report_path:
        raise ValueError("report_path is required")

    config_path = arguments.get("config_path")

    try:
        # Initialize analyzer with optional custom config
        analyzer = Analyzer(config_path) if config_path else get_analyzer()

        # Parse HTML report
        parser = HTMLParser(report_path)
        summary = parser.extract_summary()

        # For now, use empty shaders and resources
        # In a full implementation, these would be extracted from the report
        shaders = {}
        resources = []

        # Perform analysis
        result = analyzer.analyze(summary, shaders, resources)

        # Format results
        output = format_analysis_result(result)

        return [TextContent(type="text", text=output)]

    except FileNotFoundError as e:
        return [TextContent(type="text", text=f"Error: Report not found - {e}")]
    except ValueError as e:
        return [TextContent(type="text", text=f"Error: Invalid report - {e}")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: Analysis failed - {e}")]


async def get_summary(arguments: dict[str, Any]) -> list[TextContent]:
    """Extract summary information from a RenderDoc report.

    Args:
        arguments: Tool arguments containing report_path

    Returns:
        TextContent containing summary information
    """
    report_path = arguments.get("report_path")
    if not report_path:
        raise ValueError("report_path is required")

    try:
        # Parse HTML report
        parser = HTMLParser(report_path)
        summary = parser.extract_summary()

        # Format summary
        output = format_summary(summary)

        return [TextContent(type="text", text=output)]

    except FileNotFoundError as e:
        return [TextContent(type="text", text=f"Error: Report not found - {e}")]
    except ValueError as e:
        return [TextContent(type="text", text=f"Error: Invalid report - {e}")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: Summary extraction failed - {e}")]


def format_analysis_result(result) -> str:
    """Format analysis result as readable text.

    Args:
        result: AnalysisResult from analyzer

    Returns:
        Formatted text output
    """
    lines = []
    lines.append("# RenderDoc Analysis Report")
    lines.append("")

    # Summary section
    lines.append("## Summary")
    lines.append(f"- API Type: {result.summary.api_type}")
    lines.append(f"- Draw Calls: {result.summary.total_draw_calls}")
    lines.append(f"- Shaders: {result.summary.total_shaders}")
    lines.append(f"- Frames: {result.summary.frame_count}")
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
        lines.append("")

    # Metrics section
    lines.append("## Metrics")
    for key, value in result.metrics.items():
        if key != "thresholds":
            lines.append(f"- {key}: {value}")
    lines.append("")

    return "\n".join(lines)


def format_summary(summary: ReportSummary) -> str:
    """Format report summary as readable text.

    Args:
        summary: ReportSummary from parser

    Returns:
        Formatted text output
    """
    lines = []
    lines.append("# RenderDoc Report Summary")
    lines.append("")
    lines.append(f"- API Type: {summary.api_type}")
    lines.append(f"- Draw Calls: {summary.total_draw_calls}")
    lines.append(f"- Shaders: {summary.total_shaders}")
    lines.append(f"- Frames: {summary.frame_count}")
    lines.append("")

    return "\n".join(lines)


async def main():
    """Main entry point for the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="renderdoc-analyzer",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                )
            )
        )


if __name__ == "__main__":
    asyncio.run(main())
