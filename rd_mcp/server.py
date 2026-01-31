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
from rd_mcp.rdc_analyzer_cmd import analyze_rdc_file, analyze_rdc_with_mali
from rd_mcp.models import ReportSummary
from rd_mcp.rdc_analyzer_cmd import PassInfo


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
                "Requires RenderDoc to be installed. Works with any Python version. "
                "Supports preset configurations for different performance profiles. "
                "When mali_enabled is True, uses Mali Offline Compiler (malioc) to analyze "
                "shader GPU cycles and register usage for Mali GPUs."
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
                    },
                    "preset": {
                        "type": "string",
                        "enum": ["mobile-aggressive", "mobile-balanced", "pc-balanced"],
                        "description": "Optional preset configuration for performance thresholds. "
                                      "If both preset and config_path are provided, preset takes precedence."
                    },
                    "mali_enabled": {
                        "type": "boolean",
                        "description": "Enable Mali GPU shader analysis using malioc. "
                                      "When enabled, analyzes shaders for GPU cycles, register usage, "
                                      "and texture samples. Requires malioc to be installed. Default: false"
                    },
                    "mali_target_gpu": {
                        "type": "string",
                        "description": "Target Mali GPU for shader analysis. "
                                      "Examples: 'Mali-G78', 'Mali-G710', 'Mali-G720'. Default: 'Mali-G78'"
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
        arguments: Tool arguments containing rdc_path and optional config_path, preset, 
                   mali_enabled, and mali_target_gpu

    Returns:
        TextContent containing analysis results
    """
    rdc_path = arguments.get("rdc_path")
    if not rdc_path:
        return [TextContent(type="text", text="Error: rdc_path is required")]

    config_path = arguments.get("config_path")
    preset = arguments.get("preset")
    mali_enabled = arguments.get("mali_enabled", False)
    mali_target_gpu = arguments.get("mali_target_gpu", "Mali-G78")

    try:
        # Initialize analyzer with optional custom config or preset
        if preset:
            analyzer = Analyzer(preset=preset)
        else:
            from pathlib import Path
            path = Path(config_path) if config_path else None
            analyzer = Analyzer(config_path=path)

        # Analyze RDC file with optional Mali analysis
        if mali_enabled:
            rdc_data, mali_result = analyze_rdc_with_mali(
                rdc_path,
                mali_enabled=True,
                mali_target_gpu=mali_target_gpu
            )
        else:
            rdc_data = analyze_rdc_file(rdc_path)
            mali_result = None

        # Convert RDC data to analysis format
        from rd_mcp.models import ReportSummary

        summary = ReportSummary(
            api_type=rdc_data.summary.api_type,
            total_draw_calls=rdc_data.summary.total_draw_calls,
            total_shaders=rdc_data.summary.total_shaders,
            frame_count=rdc_data.summary.frame_count
        )

        # Convert shaders to dict format (use getattr for compatibility)
        # Include source for Mali complexity analysis if available
        shaders = {
            name: {
                "instruction_count": getattr(shader, 'instruction_count', 0),
                "stage": getattr(shader, 'stage', 'Unknown'),
                "binding_count": getattr(shader, 'binding_count', 0),
                "source": getattr(shader, 'source', None)
            }
            for name, shader in rdc_data.shaders.items()
        }

        # Convert textures to list format (use getattr for compatibility)
        resources = [
            {
                "name": getattr(tex, 'name', ''),
                "width": getattr(tex, 'width', 0),
                "height": getattr(tex, 'height', 0),
                "depth": getattr(tex, 'depth', 1),
                "format": getattr(tex, 'format', '')
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

        # Perform analysis with draws included
        # Note: analyzer.analyze expects (summary, shaders, resources, draws, passes)
        draws_list = rdc_data.draws if hasattr(rdc_data, 'draws') else None
        result = analyzer.analyze(summary, shaders, resources, draws_list, passes)

        # Format results (with optional Mali analysis)
        output = format_rdc_analysis_result(result, rdc_data, mali_result)

        return [TextContent(type="text", text=output)]

    except FileNotFoundError as e:
        return [TextContent(type="text", text=f"Error: RDC file not found - {e}")]
    except RuntimeError as e:
        return [TextContent(type="text", text=f"Error: {e}")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: Analysis failed - {e}")]


def format_rdc_analysis_result(result, rdc_data, mali_result=None) -> str:
    """Format RDC analysis result as readable text.

    Args:
        result: AnalysisResult from analyzer
        rdc_data: Raw RDCAnalysisData from rdc_analyzer
        mali_result: Optional MaliAnalysisResult from Mali shader analysis

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

    # Add total triangle count if model_stats available
    if result.model_stats:
        total_triangles = sum(stat.triangle_count for stat in result.model_stats.values())
        lines.append(f"- Total Triangles: {total_triangles:,}")

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

    # Model Statistics section
    lines.append("## Model Statistics")
    if result.model_stats:
        lines.append(f"Total models: {len(result.model_stats)}")
        lines.append("")

        # Sort by triangle count (descending) and take top 10
        sorted_models = sorted(
            result.model_stats.values(),
            key=lambda m: m.triangle_count,
            reverse=True
        )[:10]

        lines.append("### Top Models by Triangle Count")
        for i, model in enumerate(sorted_models, 1):
            lines.append(f"{i}. **{model.name}**")
            lines.append(f"   - Triangles: {model.triangle_count:,}")
            lines.append(f"   - Vertices: {model.vertex_count:,}")
            lines.append(f"   - Draw calls: {model.draw_calls}")
            if model.passes:
                passes_str = ", ".join(model.passes[:3])  # Show up to 3 passes
                if len(model.passes) > 3:
                    passes_str += f" (and {len(model.passes) - 3} more)"
                lines.append(f"   - Passes: {passes_str}")
        lines.append("")
    else:
        lines.append("No model statistics available.")
        lines.append("")

    # Pass Switches section
    if result.pass_switches is not None:
        lines.append("## Pass Switches")
        lines.append("### State Change Breakdown")
        lines.append(f"- Marker switches: {result.pass_switches.marker_switches}")
        lines.append(f"- FBO switches: {result.pass_switches.fbo_switches}")
        lines.append(f"- Texture binding changes: {result.pass_switches.texture_bind_changes}")
        lines.append(f"- Shader changes: {result.pass_switches.shader_changes}")
        lines.append(f"- **Total: {result.pass_switches.total}**")
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

    # Detection Errors section (if errors present)
    if result.errors:
        lines.append("## Detection Errors")
        lines.append(f"Total errors: {len(result.errors)}")
        lines.append("")
        for error in result.errors:
            lines.append(f"- {error}")
        lines.append("")

    # Mali GPU Shader Analysis section (if available)
    if mali_result is not None:
        lines.append("## Mali GPU Shader Analysis")
        lines.append("")
        
        if mali_result.malioc_available:
            lines.append(f"- Target GPU: {mali_result.target_gpu}")
            lines.append(f"- malioc Version: {mali_result.malioc_version}")
            lines.append(f"- Shaders Analyzed: {mali_result.total_shaders_analyzed}")
            lines.append(f"- Complex Shaders: {len(mali_result.complex_shaders)}")
            lines.append("")
            
            # Show slowest shaders by cycle count
            if mali_result.shaders:
                lines.append("### Slowest Shaders by GPU Cycles")
                slowest = mali_result.get_slowest_shaders(10)
                for i, shader in enumerate(slowest, 1):
                    lines.append(f"{i}. **{shader.shader_name}** ({shader.stage})")
                    lines.append(f"   - Total Cycles: {shader.total_cycles:.1f}")
                    lines.append(f"   - Arithmetic: {shader.arithmetic_cycles:.1f}, Texture: {shader.texture_cycles:.1f}, Load/Store: {shader.load_store_cycles:.1f}")
                    lines.append(f"   - Registers: {shader.work_registers} work, {shader.uniform_registers} uniform")
                    if shader.stack_spilling:
                        lines.append("   - ⚠️ Stack spilling detected!")
                    if shader.texture_samples > 0:
                        lines.append(f"   - Texture samples: {shader.texture_samples}")
                lines.append("")
            
            # Show fragment shaders specifically (most performance critical)
            fragment_shaders = mali_result.fragment_shaders
            if fragment_shaders:
                lines.append("### Fragment Shader Statistics")
                lines.append(f"Total fragment shaders: {len(fragment_shaders)}")
                avg_cycles = sum(s.total_cycles for s in fragment_shaders) / len(fragment_shaders)
                max_cycles = max(s.total_cycles for s in fragment_shaders)
                lines.append(f"- Average cycles: {avg_cycles:.1f}")
                lines.append(f"- Maximum cycles: {max_cycles:.1f}")
                lines.append("")
            
            # Show analysis errors/warnings if any
            if mali_result.errors:
                lines.append("### Mali Analysis Warnings")
                for error in mali_result.errors:
                    lines.append(f"- {error}")
                lines.append("")
        else:
            lines.append("Mali Offline Compiler (malioc) not available.")
            lines.append("")
            lines.append("To enable Mali shader analysis:")
            lines.append("1. Install ARM Mobile Studio from https://developer.arm.com/Tools%20and%20Software/Arm%20Mobile%20Studio")
            lines.append("2. Set MALIOC_PATH environment variable to point to malioc executable")
            lines.append("3. Or specify mali_malioc_path in configuration")
            lines.append("")
            
            if mali_result.errors:
                lines.append("Errors:")
                for error in mali_result.errors:
                    lines.append(f"- {error}")
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
