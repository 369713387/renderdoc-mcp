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
from rd_mcp.rdc_analyzer_cmd import analyze_rdc_file
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
        ),
        Tool(
            name="get_slowest_passes",
            description=(
                "Get the N slowest render passes from a RenderDoc HTML report. "
                "Returns pass names, durations in milliseconds, and resolutions. "
                "Useful for identifying performance bottlenecks in the rendering pipeline."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "report_path": {
                        "type": "string",
                        "description": "Path to the RenderDoc HTML report directory (containing index.html)"
                    },
                    "count": {
                        "type": "number",
                        "description": "Number of slowest passes to return (default: 5)"
                    }
                },
                "required": ["report_path"]
            }
        ),
        Tool(
            name="analyze_rdc",
            description=(
                "Analyze a RenderDoc capture file (.rdc) directly without generating HTML. "
                "Uses renderdoccmd to convert RDC to XML and extracts performance data. "
                "Returns comprehensive analysis with draw calls, shaders, textures, and issues. "
                "Requires RenderDoc to be installed. Works with any Python version."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "rdc_path": {
                        "type": "string",
                        "description": "Path to the RenderDoc capture file (.rdc)"
                    },
                    "config_path": {
                        "type": "string",
                        "description": "Optional path to custom configuration file"
                    }
                },
                "required": ["rdc_path"]
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
    elif name == "get_slowest_passes":
        return await get_slowest_passes(arguments)
    elif name == "analyze_rdc":
        return await analyze_rdc(arguments)
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
        passes = parser.extract_passes()

        # For now, use empty shaders and resources
        # In a full implementation, these would be extracted from the report
        shaders = {}
        resources = []

        # Perform analysis
        result = analyzer.analyze(summary, shaders, resources, passes)

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


async def get_slowest_passes(arguments: dict[str, Any]) -> list[TextContent]:
    """Get the N slowest render passes from a RenderDoc report.

    Args:
        arguments: Tool arguments containing report_path and optional count

    Returns:
        TextContent containing slowest passes information
    """
    report_path = arguments.get("report_path")
    if not report_path:
        raise ValueError("report_path is required")

    count = arguments.get("count")

    try:
        # Parse HTML report
        parser = HTMLParser(report_path)
        passes = parser.extract_passes()

        if not passes:
            return [TextContent(type="text", text="No pass information found in the report.")]

        # Get slowest passes
        analyzer = get_analyzer()
        slowest = analyzer.get_slowest_passes(passes, count)

        # Format output
        output = format_slowest_passes(slowest)

        return [TextContent(type="text", text=output)]

    except FileNotFoundError as e:
        return [TextContent(type="text", text=f"Error: Report not found - {e}")]
    except ValueError as e:
        return [TextContent(type="text", text=f"Error: Invalid report - {e}")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: Pass extraction failed - {e}")]


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

    # Slowest passes section
    slowest_passes = result.metrics.get("slowest_passes", [])
    if slowest_passes:
        lines.append("## Slowest Passes")
        for i, pass_info in enumerate(slowest_passes, 1):
            lines.append(f"{i}. **{pass_info['name']}** ({pass_info['resolution']})")
            lines.append(f"   Duration: {pass_info['duration_ms']:.2f}ms")
        lines.append("")

    # Metrics section
    lines.append("## Metrics")
    for key, value in result.metrics.items():
        if key not in ["thresholds", "slowest_passes"]:
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


def format_slowest_passes(passes: list) -> str:
    """Format slowest passes as readable text.

    Args:
        passes: List of PassInfo objects

    Returns:
        Formatted text output
    """
    lines = []
    lines.append("# Slowest Render Passes")
    lines.append("")

    if not passes:
        lines.append("No pass information available.")
        return "\n".join(lines)

    lines.append(f"Top {len(passes)} slowest passes:")
    lines.append("")

    for i, pass_info in enumerate(passes, 1):
        resolution_str = f" ({pass_info.resolution})" if pass_info.resolution else ""
        lines.append(f"{i}. **{pass_info.name}**{resolution_str}")
        lines.append(f"   Duration: {pass_info.duration_ms:.2f}ms")
    lines.append("")

    return "\n".join(lines)


async def analyze_rdc(arguments: dict[str, Any]) -> list[TextContent]:
    """Analyze a RenderDoc capture file (.rdc) directly.

    Args:
        arguments: Tool arguments containing rdc_path and optional config_path

    Returns:
        TextContent containing analysis results
    """
    rdc_path = arguments.get("rdc_path")
    if not rdc_path:
        return [TextContent(type="text", text="Error: rdc_path is required")]

    config_path = arguments.get("config_path")

    try:
        # Initialize analyzer with optional custom config
        from pathlib import Path
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
                "binding_count": shader.binding_count
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

        # Perform analysis
        result = analyzer.analyze(summary, shaders, resources, passes)

        # Format results
        output = format_rdc_analysis_result(result, rdc_data)

        return [TextContent(type="text", text=output)]

    except FileNotFoundError as e:
        return [TextContent(type="text", text=f"Error: RDC file not found - {e}")]
    except RuntimeError as e:
        return [TextContent(type="text", text=f"Error: {e}")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: Analysis failed - {e}")]


def format_rdc_analysis_result(result, rdc_data) -> str:
    """Format RDC analysis result as readable text.

    Args:
        result: AnalysisResult from analyzer
        rdc_data: Raw RDCAnalysisData from rdc_analyzer

    Returns:
        Formatted text output
    """
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
