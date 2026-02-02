# rd_mcp/report_generator.py
"""Report generator for RenderDoc analysis results.

This module generates JSON and Markdown format reports from analysis results.
Supports comprehensive reporting with:
- Full data listings (no truncation)
- Statistical summaries with distributions
- Distribution histograms (text-based)
- Extended state and configuration information
"""
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Optional, Any, Dict, List, Tuple
from dataclasses import asdict, is_dataclass
from collections import Counter


def _to_serializable(obj: Any) -> Any:
    """Convert object to JSON-serializable format."""
    if is_dataclass(obj) and not isinstance(obj, type):
        return {k: _to_serializable(v) for k, v in asdict(obj).items()}
    elif isinstance(obj, dict):
        return {k: _to_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_to_serializable(item) for item in obj]
    elif hasattr(obj, '__dict__'):
        return {k: _to_serializable(v) for k, v in obj.__dict__.items() 
                if not k.startswith('_')}
    else:
        return obj


def _generate_histogram(values: List[float], bins: int = 10, width: int = 40) -> List[str]:
    """Generate a text-based histogram.
    
    Args:
        values: List of numeric values
        bins: Number of bins for the histogram
        width: Maximum width of the histogram bars
        
    Returns:
        List of strings representing the histogram
    """
    if not values:
        return ["  (No data)"]
    
    min_val = min(values)
    max_val = max(values)
    
    if min_val == max_val:
        return [f"  All values: {min_val:.2f} (count: {len(values)})"]
    
    bin_width = (max_val - min_val) / bins
    bin_counts = [0] * bins
    
    for v in values:
        bin_idx = min(int((v - min_val) / bin_width), bins - 1)
        bin_counts[bin_idx] += 1
    
    max_count = max(bin_counts) if bin_counts else 1
    lines = []
    
    for i, count in enumerate(bin_counts):
        bin_start = min_val + i * bin_width
        bin_end = bin_start + bin_width
        bar_len = int((count / max_count) * width) if max_count > 0 else 0
        bar = "█" * bar_len
        lines.append(f"  {bin_start:8.2f} - {bin_end:8.2f} | {bar} ({count})")
    
    return lines


def _calculate_stats(values: List[float]) -> Dict[str, float]:
    """Calculate statistical summary for a list of values."""
    if not values:
        return {"count": 0, "min": 0, "max": 0, "mean": 0, "median": 0, "total": 0}
    
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    total = sum(sorted_vals)
    mean = total / n
    
    if n % 2 == 0:
        median = (sorted_vals[n//2 - 1] + sorted_vals[n//2]) / 2
    else:
        median = sorted_vals[n//2]
    
    # Calculate percentiles
    p90_idx = int(n * 0.9)
    p95_idx = int(n * 0.95)
    p99_idx = int(n * 0.99)
    
    return {
        "count": n,
        "min": sorted_vals[0],
        "max": sorted_vals[-1],
        "mean": mean,
        "median": median,
        "total": total,
        "p90": sorted_vals[min(p90_idx, n-1)],
        "p95": sorted_vals[min(p95_idx, n-1)],
        "p99": sorted_vals[min(p99_idx, n-1)]
    }


class ReportGenerator:
    """Generates analysis reports in various formats."""
    
    def __init__(self, rdc_path: str, result: Any, rdc_data: Any, 
                 mali_result: Optional[Any] = None):
        """Initialize the report generator.
        
        Args:
            rdc_path: Path to the analyzed RDC file
            result: AnalysisResult from analyzer
            rdc_data: Raw RDCAnalysisData from rdc_analyzer
            mali_result: Optional MaliAnalysisResult from Mali shader analysis
        """
        self.rdc_path = rdc_path
        self.result = result
        self.rdc_data = rdc_data
        self.mali_result = mali_result
        self.timestamp = datetime.now()
    
    def generate_report_data(self) -> Dict[str, Any]:
        """Generate structured report data (complete, no truncation).
        
        Returns:
            Dictionary containing all analysis data
        """
        data = {
            "meta": {
                "rdc_file": str(self.rdc_path),
                "analysis_time": self.timestamp.isoformat(),
                "tool_version": "2.0.0"
            },
            "summary": self._generate_summary_data(),
            "statistics": self._generate_statistics_data(),
            "issues": self._generate_issues_data(),
            "model_stats": self._generate_model_data(),
            "render_passes": self._generate_pass_data(),
            "draw_calls": self._generate_drawcall_data(),
            "shaders": self._generate_shader_data(),
            "textures": self._generate_texture_data(),
            "render_states": self._generate_render_state_data(),
            "samplers": self._generate_sampler_data(),
            "framebuffers": self._generate_framebuffer_data(),
            "pass_dependencies": self._generate_dependency_data()
        }
        
        # Mali analysis results
        if self.mali_result is not None:
            data["mali_analysis"] = self._generate_mali_data()
        
        return data
    
    def _generate_summary_data(self) -> Dict[str, Any]:
        """Generate summary section data."""
        summary = {
            "api_type": self.result.summary.api_type,
            "total_draw_calls": self.result.summary.total_draw_calls,
            "total_shaders": self.result.summary.total_shaders,
            "total_textures": len(self.rdc_data.textures),
            "total_passes": len(self.rdc_data.passes),
            "frame_count": self.result.summary.frame_count
        }
        
        # Total triangles
        if self.result.model_stats:
            total_triangles = sum(stat.triangle_count for stat in self.result.model_stats.values())
            summary["total_triangles"] = total_triangles
            summary["total_models"] = len(self.result.model_stats)
        
        # Total GPU time
        if self.rdc_data.draws:
            total_gpu_ms = sum(d.gpu_duration_ms for d in self.rdc_data.draws)
            summary["total_gpu_time_ms"] = total_gpu_ms
        
        # Total texture memory
        if self.rdc_data.textures:
            total_mem = sum(t.estimate_memory() for t in self.rdc_data.textures)
            summary["total_texture_memory_mb"] = total_mem / (1024 * 1024)
        
        # Framebuffers and samplers
        summary["total_framebuffers"] = len(getattr(self.rdc_data, 'framebuffers', {}))
        summary["total_samplers"] = len(getattr(self.rdc_data, 'samplers', []))
        
        return summary
    
    def _generate_statistics_data(self) -> Dict[str, Any]:
        """Generate statistical summaries with distributions."""
        stats = {}
        
        # DrawCall duration stats
        if self.rdc_data.draws:
            durations = [d.gpu_duration_ms for d in self.rdc_data.draws if d.gpu_duration_ms > 0]
            if durations:
                stats["drawcall_duration_ms"] = _calculate_stats(durations)
        
        # Triangle count stats
        if self.result.model_stats:
            tri_counts = [float(m.triangle_count) for m in self.result.model_stats.values()]
            if tri_counts:
                stats["triangle_counts"] = _calculate_stats(tri_counts)
        
        # Pass duration stats
        if self.rdc_data.passes:
            pass_durations = [p.duration_ms for p in self.rdc_data.passes if p.duration_ms > 0]
            if pass_durations:
                stats["pass_duration_ms"] = _calculate_stats(pass_durations)
        
        # Texture memory stats
        if self.rdc_data.textures:
            tex_sizes = [t.estimate_memory() / 1024 for t in self.rdc_data.textures]  # KB
            if tex_sizes:
                stats["texture_size_kb"] = _calculate_stats(tex_sizes)
        
        # Mali cycles stats
        if self.mali_result and self.mali_result.shaders:
            cycles = [s.total_cycles for s in self.mali_result.shaders]
            stats["shader_cycles"] = _calculate_stats(cycles)
        
        return stats
    
    def _generate_issues_data(self) -> Dict[str, Any]:
        """Generate issues section data."""
        issues_data = {
            "total": self.result.metrics.get("total_issues", 0),
            "critical": [],
            "warnings": [],
            "suggestions": []
        }
        
        for severity in ["critical", "warnings", "suggestions"]:
            issues = self.result.issues.get(severity, [])
            for issue in issues:
                issues_data[severity].append({
                    "type": issue.type,
                    "description": issue.description,
                    "location": issue.location,
                    "impact": getattr(issue, 'impact', None)
                })
        
        return issues_data
    
    def _generate_model_data(self) -> List[Dict[str, Any]]:
        """Generate complete model statistics list."""
        if not self.result.model_stats:
            return []
        
        sorted_models = sorted(
            self.result.model_stats.values(),
            key=lambda m: m.triangle_count,
            reverse=True
        )
        
        return [{
            "name": model.name,
            "triangle_count": model.triangle_count,
            "vertex_count": model.vertex_count,
            "draw_calls": model.draw_calls,
            "passes": list(model.passes) if model.passes else []
        } for model in sorted_models]
    
    def _generate_pass_data(self) -> List[Dict[str, Any]]:
        """Generate complete render pass list."""
        if not self.rdc_data.passes:
            return []
        
        sorted_passes = sorted(self.rdc_data.passes, key=lambda p: p.duration_ms, reverse=True)
        
        return [{
            "name": p.name,
            "pass_index": getattr(p, 'pass_index', i),
            "draw_count": p.draw_count,
            "triangle_count": getattr(p, 'triangle_count', 0),
            "duration_ms": p.duration_ms,
            "resolution": p.resolution,
            "fbo_id": getattr(p, 'fbo_id', ''),
            "input_textures": getattr(p, 'input_textures', []),
            "output_textures": getattr(p, 'output_textures', [])
        } for i, p in enumerate(sorted_passes)]
    
    def _generate_drawcall_data(self) -> List[Dict[str, Any]]:
        """Generate complete draw call list."""
        if not self.rdc_data.draws:
            return []
        
        sorted_draws = sorted(self.rdc_data.draws, key=lambda d: d.gpu_duration_ms, reverse=True)
        
        result = []
        for draw in sorted_draws:
            dc_data = {
                "draw_id": draw.draw_id,
                "event_id": getattr(draw, 'event_id', draw.draw_id),
                "name": draw.name,
                "gpu_duration_ms": draw.gpu_duration_ms,
                "vertex_count": draw.vertex_count,
                "index_count": getattr(draw, 'index_count', 0),
                "instance_count": getattr(draw, 'instance_count', 1),
                "triangle_count": getattr(draw, 'triangle_count', 0),
                "marker": draw.marker,
                "shader_program": getattr(draw, 'shader_program', ''),
                "fbo_id": getattr(draw, 'fbo_id', ''),
                "bound_textures": getattr(draw, 'bound_textures', [])
            }
            
            # Include render state if available
            state = getattr(draw, 'state', None)
            if state:
                dc_data["state"] = {
                    "blend_enabled": state.blend.enabled if hasattr(state, 'blend') and state.blend else False,
                    "depth_test": state.depth.test_enabled if hasattr(state, 'depth') and state.depth else False,
                    "depth_write": state.depth.write_enabled if hasattr(state, 'depth') and state.depth else True,
                    "cull_enabled": state.cull.enabled if hasattr(state, 'cull') and state.cull else False,
                    "cull_mode": state.cull.mode if hasattr(state, 'cull') and state.cull else "BACK"
                }
            
            result.append(dc_data)
        
        return result
    
    def _generate_shader_data(self) -> List[Dict[str, Any]]:
        """Generate complete shader list."""
        result = []
        for name, shader in self.rdc_data.shaders.items():
            shader_data = {
                "name": name,
                "stage": getattr(shader, 'stage', 'Unknown'),
                "instruction_count": getattr(shader, 'instruction_count', 0),
                "source_length": getattr(shader, 'source_length', 0),
                "binding_count": getattr(shader, 'binding_count', 0)
            }
            result.append(shader_data)
        return result
    
    def _generate_texture_data(self) -> List[Dict[str, Any]]:
        """Generate complete texture list."""
        result = []
        for tex in self.rdc_data.textures:
            tex.estimate_memory()  # Ensure memory is calculated
            tex_data = {
                "resource_id": getattr(tex, 'resource_id', ''),
                "name": getattr(tex, 'name', ''),
                "width": getattr(tex, 'width', 0),
                "height": getattr(tex, 'height', 0),
                "depth": getattr(tex, 'depth', 1),
                "format": getattr(tex, 'format', ''),
                "mip_levels": getattr(tex, 'mip_levels', 1),
                "array_size": getattr(tex, 'array_size', 1),
                "samples": getattr(tex, 'samples', 1),
                "memory_size_bytes": getattr(tex, 'memory_size', 0),
                "memory_size_mb": tex.memory_size_mb,
                "is_compressed": getattr(tex, 'is_compressed', False)
            }
            result.append(tex_data)
        
        # Sort by memory size
        result.sort(key=lambda t: t["memory_size_bytes"], reverse=True)
        return result
    
    def _generate_render_state_data(self) -> Dict[str, Any]:
        """Generate render state statistics."""
        if not self.rdc_data.draws:
            return {}
        
        # Check if any draw has state info
        has_state = any(hasattr(d, 'state') and d.state for d in self.rdc_data.draws)
        if not has_state:
            return {"tracking_enabled": False}
        
        total = len(self.rdc_data.draws)
        blend_enabled = sum(1 for d in self.rdc_data.draws 
                          if hasattr(d, 'state') and d.state and 
                          hasattr(d.state, 'blend') and d.state.blend and d.state.blend.enabled)
        depth_test = sum(1 for d in self.rdc_data.draws 
                        if hasattr(d, 'state') and d.state and 
                        hasattr(d.state, 'depth') and d.state.depth and d.state.depth.test_enabled)
        depth_write = sum(1 for d in self.rdc_data.draws 
                         if hasattr(d, 'state') and d.state and 
                         hasattr(d.state, 'depth') and d.state.depth and d.state.depth.write_enabled)
        cull_enabled = sum(1 for d in self.rdc_data.draws 
                          if hasattr(d, 'state') and d.state and 
                          hasattr(d.state, 'cull') and d.state.cull and d.state.cull.enabled)
        
        # Count blend modes
        blend_modes = Counter()
        depth_funcs = Counter()
        cull_modes = Counter()
        
        for draw in self.rdc_data.draws:
            state = getattr(draw, 'state', None)
            if state:
                blend = getattr(state, 'blend', None)
                depth = getattr(state, 'depth', None)
                cull = getattr(state, 'cull', None)
                
                if blend and blend.enabled:
                    mode = f"{blend.src_rgb}/{blend.dst_rgb}"
                    blend_modes[mode] += 1
                if depth and depth.test_enabled:
                    depth_funcs[depth.func] += 1
                if cull and cull.enabled:
                    cull_modes[cull.mode] += 1
        
        return {
            "tracking_enabled": True,
            "total_draws": total,
            "blend_enabled_count": blend_enabled,
            "blend_enabled_percent": (blend_enabled / total * 100) if total else 0,
            "depth_test_count": depth_test,
            "depth_test_percent": (depth_test / total * 100) if total else 0,
            "depth_write_count": depth_write,
            "depth_write_percent": (depth_write / total * 100) if total else 0,
            "cull_enabled_count": cull_enabled,
            "cull_enabled_percent": (cull_enabled / total * 100) if total else 0,
            "blend_modes": dict(blend_modes.most_common(10)),
            "depth_functions": dict(depth_funcs.most_common()),
            "cull_modes": dict(cull_modes.most_common())
        }
    
    def _generate_sampler_data(self) -> List[Dict[str, Any]]:
        """Generate complete sampler list."""
        samplers = getattr(self.rdc_data, 'samplers', [])
        return [{
            "sampler_id": getattr(s, 'sampler_id', ''),
            "texture_id": getattr(s, 'texture_id', ''),
            "min_filter": getattr(s, 'min_filter', ''),
            "mag_filter": getattr(s, 'mag_filter', ''),
            "wrap_s": getattr(s, 'wrap_s', ''),
            "wrap_t": getattr(s, 'wrap_t', ''),
            "wrap_r": getattr(s, 'wrap_r', ''),
            "anisotropy": getattr(s, 'anisotropy', 1.0)
        } for s in samplers]
    
    def _generate_framebuffer_data(self) -> List[Dict[str, Any]]:
        """Generate complete framebuffer list."""
        framebuffers = getattr(self.rdc_data, 'framebuffers', {})
        result = []
        for fbo_id, fbo in framebuffers.items():
            color_atts = []
            if hasattr(fbo, 'color_attachments'):
                for att in fbo.color_attachments:
                    color_atts.append({
                        "attachment": getattr(att, 'attachment', ''),
                        "texture_id": getattr(att, 'texture_id', ''),
                        "format": getattr(att, 'format', '')
                    })
            
            fbo_data = {
                "fbo_id": str(fbo_id),
                "name": getattr(fbo, 'name', ''),
                "is_default": getattr(fbo, 'is_default', False),
                "width": getattr(fbo, 'width', 0),
                "height": getattr(fbo, 'height', 0),
                "color_attachments": color_atts,
                "has_depth": (hasattr(fbo, 'depth_attachment') and fbo.depth_attachment is not None) or \
                            (hasattr(fbo, 'depth_stencil_attachment') and fbo.depth_stencil_attachment is not None),
                "has_stencil": (hasattr(fbo, 'stencil_attachment') and fbo.stencil_attachment is not None) or \
                              (hasattr(fbo, 'depth_stencil_attachment') and fbo.depth_stencil_attachment is not None),
                "clear_count": len(getattr(fbo, 'clear_ops', []))
            }
            result.append(fbo_data)
        return result
    
    def _generate_dependency_data(self) -> List[Dict[str, Any]]:
        """Generate pass dependency list."""
        dependencies = getattr(self.rdc_data, 'pass_dependencies', [])
        return [{
            "source_pass": getattr(d, 'source_pass', ''),
            "source_pass_index": getattr(d, 'source_pass_index', -1),
            "target_pass": getattr(d, 'target_pass', ''),
            "target_pass_index": getattr(d, 'target_pass_index', -1),
            "resource_type": getattr(d, 'resource_type', ''),
            "resource_id": getattr(d, 'resource_id', ''),
            "dependency_type": getattr(d, 'dependency_type', '')
        } for d in dependencies]
    
    def _generate_mali_data(self) -> Dict[str, Any]:
        """Generate complete Mali analysis data."""
        mali_data = {
            "available": self.mali_result.malioc_available,
            "target_gpu": self.mali_result.target_gpu,
            "malioc_version": self.mali_result.malioc_version,
            "total_shaders_analyzed": self.mali_result.total_shaders_analyzed,
            "complex_shaders_count": len(self.mali_result.complex_shaders),
            "shader_analysis": [],
            "statistics": {},
            "errors": self.mali_result.errors
        }
        
        if self.mali_result.shaders:
            # Sort by total cycles and include ALL shaders
            sorted_shaders = sorted(
                self.mali_result.shaders, 
                key=lambda s: s.total_cycles, 
                reverse=True
            )
            
            for shader in sorted_shaders:
                mali_data["shader_analysis"].append({
                    "name": shader.shader_name,
                    "stage": shader.stage,
                    "total_cycles": shader.total_cycles,
                    "arithmetic_cycles": shader.arithmetic_cycles,
                    "texture_cycles": shader.texture_cycles,
                    "load_store_cycles": shader.load_store_cycles,
                    "varying_cycles": getattr(shader, 'varying_cycles', 0),
                    "work_registers": shader.work_registers,
                    "uniform_registers": shader.uniform_registers,
                    "stack_spilling": shader.stack_spilling,
                    "texture_samples": shader.texture_samples,
                    "is_complex": shader in self.mali_result.complex_shaders
                })
            
            # Statistics
            cycles = [s.total_cycles for s in self.mali_result.shaders]
            mali_data["statistics"]["cycles"] = _calculate_stats(cycles)
            
            # Fragment shader stats
            fragment_shaders = self.mali_result.fragment_shaders
            if fragment_shaders:
                frag_cycles = [s.total_cycles for s in fragment_shaders]
                mali_data["statistics"]["fragment_cycles"] = _calculate_stats(frag_cycles)
            
            # Vertex shader stats
            vertex_shaders = [s for s in self.mali_result.shaders if s.stage == "Vertex"]
            if vertex_shaders:
                vert_cycles = [s.total_cycles for s in vertex_shaders]
                mali_data["statistics"]["vertex_cycles"] = _calculate_stats(vert_cycles)
        
        return mali_data
    
    def save_json(self, output_path: Path) -> Path:
        """Save report as JSON file.
        
        Args:
            output_path: Directory to save the report
            
        Returns:
            Path to the generated JSON file
        """
        output_path = Path(output_path)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Generate filename from RDC file
        rdc_name = Path(self.rdc_path).stem
        timestamp = self.timestamp.strftime("%Y%m%d_%H%M%S")
        json_file = output_path / f"{rdc_name}_analysis_{timestamp}.json"
        
        data = self.generate_report_data()
        
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return json_file
    
    def save_markdown(self, output_path: Path) -> Path:
        """Save report as Markdown file.
        
        Args:
            output_path: Directory to save the report
            
        Returns:
            Path to the generated Markdown file
        """
        output_path = Path(output_path)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Generate filename from RDC file
        rdc_name = Path(self.rdc_path).stem
        timestamp = self.timestamp.strftime("%Y%m%d_%H%M%S")
        md_file = output_path / f"{rdc_name}_analysis_{timestamp}.md"
        
        lines = self._generate_markdown_content()
        
        with open(md_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        
        return md_file
    
    def _generate_markdown_content(self) -> List[str]:
        """Generate comprehensive Markdown content for the report.
        
        Returns:
            List of lines for the Markdown file
        """
        lines = []
        
        # Build report sections
        lines.extend(self._md_header())
        lines.extend(self._md_summary())
        lines.extend(self._md_issues())
        lines.extend(self._md_shader_analysis())
        lines.extend(self._md_mali_analysis())
        lines.extend(self._md_model_statistics())
        lines.extend(self._md_pass_analysis())
        lines.extend(self._md_drawcall_analysis())
        lines.extend(self._md_texture_analysis())
        lines.extend(self._md_render_state_analysis())
        lines.extend(self._md_framebuffer_analysis())
        lines.extend(self._md_dependency_analysis())
        lines.extend(self._md_footer())
        
        return lines
    
    def _md_header(self) -> List[str]:
        """Generate Markdown header."""
        return [
            "# 📊 RenderDoc Performance Analysis Report",
            "",
            f"> **Generated**: {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            f"> **RDC File**: `{Path(self.rdc_path).name}`",
            "",
            "---",
            ""
        ]
    
    def _md_summary(self) -> List[str]:
        """Generate summary section."""
        lines = [
            "## 📈 Executive Summary",
            "",
            "| Metric | Value |",
            "|--------|-------|"
        ]
        
        lines.append(f"| API Type | {self.result.summary.api_type} |")
        lines.append(f"| Draw Calls | {self.result.summary.total_draw_calls:,} |")
        lines.append(f"| Shaders | {self.result.summary.total_shaders:,} |")
        lines.append(f"| Textures | {len(self.rdc_data.textures):,} |")
        lines.append(f"| Render Passes | {len(self.rdc_data.passes):,} |")
        
        if self.result.model_stats:
            total_tris = sum(m.triangle_count for m in self.result.model_stats.values())
            lines.append(f"| Total Triangles | {total_tris:,} |")
            lines.append(f"| Models | {len(self.result.model_stats):,} |")
        
        if self.rdc_data.draws:
            total_gpu = sum(d.gpu_duration_ms for d in self.rdc_data.draws)
            lines.append(f"| Total GPU Time | {total_gpu:.2f} ms |")
        
        if self.rdc_data.textures:
            total_mem = sum(t.estimate_memory() for t in self.rdc_data.textures) / (1024*1024)
            lines.append(f"| Texture Memory | {total_mem:.2f} MB |")
        
        lines.append("")
        return lines
    
    def _md_issues(self) -> List[str]:
        """Generate issues section."""
        total_issues = self.result.metrics.get("total_issues", 0)
        lines = [f"## ⚠️ Issues Found: {total_issues}", ""]
        
        for severity, emoji in [("critical", "🔴"), ("warnings", "🟡"), ("suggestions", "🟢")]:
            issues = self.result.issues.get(severity, [])
            if issues:
                lines.append(f"### {emoji} {severity.title()} ({len(issues)})")
                lines.append("")
                for issue in issues:
                    lines.append(f"- **{issue.type}**: {issue.description}")
                    lines.append(f"  - Location: `{issue.location}`")
                    if hasattr(issue, 'impact') and issue.impact:
                        lines.append(f"  - Impact: {issue.impact}")
                lines.append("")
        
        return lines
    
    def _md_shader_analysis(self) -> List[str]:
        """Generate complete shader analysis section."""
        lines = [
            "## 🎨 Shader Analysis",
            "",
            f"**Total Shaders**: {self.result.summary.total_shaders}",
            ""
        ]
        
        if not self.rdc_data.shaders:
            lines.append("No shader data available.")
            lines.append("")
            return lines
        
        # Stage distribution
        stages = Counter(getattr(s, 'stage', 'Unknown') for s in self.rdc_data.shaders.values())
        lines.append("### Stage Distribution")
        lines.append("")
        for stage, count in stages.most_common():
            lines.append(f"- {stage}: {count}")
        lines.append("")
        
        # Complete shader list
        lines.append("### Complete Shader List")
        lines.append("")
        lines.append("<details>")
        lines.append("<summary>Click to expand full shader list</summary>")
        lines.append("")
        lines.append("| # | Shader Name | Stage | Instructions |")
        lines.append("|---|-------------|-------|--------------|")
        
        for i, (name, shader) in enumerate(self.rdc_data.shaders.items(), 1):
            stage = getattr(shader, 'stage', 'Unknown')
            instr = getattr(shader, 'instruction_count', 0)
            display_name = name[:50] + "..." if len(name) > 50 else name
            lines.append(f"| {i} | {display_name} | {stage} | {instr:,} |")
        
        lines.append("")
        lines.append("</details>")
        lines.append("")
        
        return lines
    
    def _md_mali_analysis(self) -> List[str]:
        """Generate comprehensive Mali GPU analysis section."""
        if self.mali_result is None:
            return []
        
        lines = [
            "## 📱 Mali GPU Shader Analysis",
            ""
        ]
        
        if not self.mali_result.malioc_available:
            lines.append("⚠️ Mali Offline Compiler (malioc) not available.")
            lines.append("")
            return lines
        
        lines.append(f"- **Target GPU**: {self.mali_result.target_gpu}")
        lines.append(f"- **malioc Version**: {self.mali_result.malioc_version}")
        lines.append(f"- **Shaders Analyzed**: {self.mali_result.total_shaders_analyzed}")
        lines.append(f"- **Complex Shaders**: {len(self.mali_result.complex_shaders)}")
        lines.append("")
        
        if not self.mali_result.shaders:
            return lines
        
        # Statistics
        cycles = [s.total_cycles for s in self.mali_result.shaders]
        stats = _calculate_stats(cycles)
        
        lines.append("### Cycle Statistics")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Min Cycles | {stats['min']:.1f} |")
        lines.append(f"| Max Cycles | {stats['max']:.1f} |")
        lines.append(f"| Mean Cycles | {stats['mean']:.1f} |")
        lines.append(f"| Median Cycles | {stats['median']:.1f} |")
        lines.append(f"| P90 Cycles | {stats['p90']:.1f} |")
        lines.append(f"| P95 Cycles | {stats['p95']:.1f} |")
        lines.append("")
        
        # Histogram
        lines.append("### Cycle Distribution")
        lines.append("")
        lines.append("```")
        lines.extend(_generate_histogram(cycles, bins=10, width=30))
        lines.append("```")
        lines.append("")
        
        # Complete shader list
        lines.append("### Complete Mali Shader Analysis")
        lines.append("")
        lines.append("<details>")
        lines.append("<summary>Click to expand full shader analysis</summary>")
        lines.append("")
        lines.append("| # | Shader | Stage | Total | Arith | Tex | L/S | Regs | Spill |")
        lines.append("|---|--------|-------|-------|-------|-----|-----|------|-------|")
        
        sorted_shaders = sorted(self.mali_result.shaders, key=lambda s: s.total_cycles, reverse=True)
        for i, shader in enumerate(sorted_shaders, 1):
            name = shader.shader_name[:30] + "..." if len(shader.shader_name) > 30 else shader.shader_name
            regs = f"{shader.work_registers}W"
            spill = "⚠️" if shader.stack_spilling else "✓"
            lines.append(f"| {i} | {name} | {shader.stage} | {shader.total_cycles:.1f} | {shader.arithmetic_cycles:.1f} | {shader.texture_cycles:.1f} | {shader.load_store_cycles:.1f} | {regs} | {spill} |")
        
        lines.append("")
        lines.append("</details>")
        lines.append("")
        
        return lines
    
    def _md_model_statistics(self) -> List[str]:
        """Generate complete model statistics section."""
        lines = ["## 🗿 Model Statistics", ""]
        
        if not self.result.model_stats:
            lines.append("No model data available.")
            lines.append("")
            return lines
        
        models = list(self.result.model_stats.values())
        total_tris = sum(m.triangle_count for m in models)
        
        lines.append(f"**Total Models**: {len(models)}")
        lines.append(f"**Total Triangles**: {total_tris:,}")
        lines.append("")
        
        # Statistics
        tri_counts = [float(m.triangle_count) for m in models]
        stats = _calculate_stats(tri_counts)
        
        lines.append("### Triangle Count Statistics")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Min | {int(stats['min']):,} |")
        lines.append(f"| Max | {int(stats['max']):,} |")
        lines.append(f"| Mean | {int(stats['mean']):,} |")
        lines.append(f"| Median | {int(stats['median']):,} |")
        lines.append("")
        
        # Histogram
        lines.append("### Triangle Distribution")
        lines.append("")
        lines.append("```")
        lines.extend(_generate_histogram(tri_counts, bins=10, width=30))
        lines.append("```")
        lines.append("")
        
        # Complete list
        lines.append("### Complete Model List")
        lines.append("")
        lines.append("<details>")
        lines.append("<summary>Click to expand full model list</summary>")
        lines.append("")
        lines.append("| # | Model | Triangles | Vertices | Draws |")
        lines.append("|---|-------|-----------|----------|-------|")
        
        sorted_models = sorted(models, key=lambda m: m.triangle_count, reverse=True)
        for i, model in enumerate(sorted_models, 1):
            name = model.name[:40] + "..." if len(model.name) > 40 else model.name
            lines.append(f"| {i} | {name} | {model.triangle_count:,} | {model.vertex_count:,} | {model.draw_calls} |")
        
        lines.append("")
        lines.append("</details>")
        lines.append("")
        
        return lines
    
    def _md_pass_analysis(self) -> List[str]:
        """Generate complete pass analysis section."""
        lines = ["## 🎬 Render Pass Analysis", ""]
        
        if not self.rdc_data.passes:
            lines.append("No pass data available.")
            lines.append("")
            return lines
        
        passes = self.rdc_data.passes
        total_duration = sum(p.duration_ms for p in passes)
        
        lines.append(f"**Total Passes**: {len(passes)}")
        lines.append(f"**Total Duration**: {total_duration:.2f} ms")
        lines.append("")
        
        # Statistics
        durations = [p.duration_ms for p in passes if p.duration_ms > 0]
        if durations:
            stats = _calculate_stats(durations)
            
            lines.append("### Duration Statistics")
            lines.append("")
            lines.append("| Metric | Value (ms) |")
            lines.append("|--------|------------|")
            lines.append(f"| Min | {stats['min']:.3f} |")
            lines.append(f"| Max | {stats['max']:.3f} |")
            lines.append(f"| Mean | {stats['mean']:.3f} |")
            lines.append(f"| Median | {stats['median']:.3f} |")
            lines.append("")
            
            # Histogram
            lines.append("### Duration Distribution")
            lines.append("")
            lines.append("```")
            lines.extend(_generate_histogram(durations, bins=10, width=30))
            lines.append("```")
            lines.append("")
        
        # Complete list
        lines.append("### Complete Pass List")
        lines.append("")
        lines.append("<details>")
        lines.append("<summary>Click to expand full pass list</summary>")
        lines.append("")
        lines.append("| # | Pass Name | Draws | Duration (ms) | Resolution |")
        lines.append("|---|-----------|-------|---------------|------------|")
        
        sorted_passes = sorted(passes, key=lambda p: p.duration_ms, reverse=True)
        for i, p in enumerate(sorted_passes, 1):
            name = p.name[:35] + "..." if len(p.name) > 35 else p.name
            resolution = p.resolution or "-"
            lines.append(f"| {i} | {name} | {p.draw_count} | {p.duration_ms:.3f} | {resolution} |")
        
        lines.append("")
        lines.append("</details>")
        lines.append("")
        
        return lines
    
    def _md_drawcall_analysis(self) -> List[str]:
        """Generate complete draw call analysis section."""
        lines = ["## ⏱️ Draw Call Analysis", ""]
        
        if not self.rdc_data.draws:
            lines.append("No draw call data available.")
            lines.append("")
            return lines
        
        draws = self.rdc_data.draws
        total_duration = sum(d.gpu_duration_ms for d in draws)
        
        lines.append(f"**Total Draw Calls**: {len(draws)}")
        lines.append(f"**Total GPU Time**: {total_duration:.2f} ms")
        lines.append("")
        
        # Statistics
        durations = [d.gpu_duration_ms for d in draws if d.gpu_duration_ms > 0]
        if durations:
            stats = _calculate_stats(durations)
            
            lines.append("### Duration Statistics")
            lines.append("")
            lines.append("| Metric | Value (ms) |")
            lines.append("|--------|------------|")
            lines.append(f"| Min | {stats['min']:.4f} |")
            lines.append(f"| Max | {stats['max']:.4f} |")
            lines.append(f"| Mean | {stats['mean']:.4f} |")
            lines.append(f"| Median | {stats['median']:.4f} |")
            lines.append(f"| P90 | {stats['p90']:.4f} |")
            lines.append(f"| P99 | {stats['p99']:.4f} |")
            lines.append("")
            
            # Histogram
            lines.append("### Duration Distribution")
            lines.append("")
            lines.append("```")
            lines.extend(_generate_histogram(durations, bins=10, width=30))
            lines.append("```")
            lines.append("")
        
        # Complete list
        lines.append("### Complete Draw Call List")
        lines.append("")
        lines.append("<details>")
        lines.append("<summary>Click to expand full draw call list</summary>")
        lines.append("")
        lines.append("| # | ID | Call | Duration (ms) | Verts | Marker |")
        lines.append("|---|-----|------|---------------|-------|--------|")
        
        sorted_draws = sorted(draws, key=lambda d: d.gpu_duration_ms, reverse=True)
        for i, d in enumerate(sorted_draws, 1):
            marker = (d.marker[:20] + "...") if d.marker and len(d.marker) > 20 else (d.marker or "-")
            lines.append(f"| {i} | {d.draw_id} | {d.name} | {d.gpu_duration_ms:.4f} | {d.vertex_count:,} | {marker} |")
        
        lines.append("")
        lines.append("</details>")
        lines.append("")
        
        return lines
    
    def _md_texture_analysis(self) -> List[str]:
        """Generate complete texture analysis section."""
        lines = ["## 🖼️ Texture Analysis", ""]
        
        if not self.rdc_data.textures:
            lines.append("No texture data available.")
            lines.append("")
            return lines
        
        textures = self.rdc_data.textures
        for t in textures:
            t.estimate_memory()
        
        total_mem = sum(t.memory_size for t in textures) / (1024*1024)
        
        lines.append(f"**Total Textures**: {len(textures)}")
        lines.append(f"**Total Memory**: {total_mem:.2f} MB")
        lines.append("")
        
        # Statistics
        sizes_kb = [t.memory_size / 1024 for t in textures]
        if sizes_kb:
            stats = _calculate_stats(sizes_kb)
            
            lines.append("### Memory Statistics (KB)")
            lines.append("")
            lines.append("| Metric | Value |")
            lines.append("|--------|-------|")
            lines.append(f"| Min | {stats['min']:.2f} |")
            lines.append(f"| Max | {stats['max']:.2f} |")
            lines.append(f"| Mean | {stats['mean']:.2f} |")
            lines.append(f"| Median | {stats['median']:.2f} |")
            lines.append("")
            
            # Histogram
            lines.append("### Memory Distribution")
            lines.append("")
            lines.append("```")
            lines.extend(_generate_histogram(sizes_kb, bins=10, width=30))
            lines.append("```")
            lines.append("")
        
        # Format distribution
        formats = Counter(t.format for t in textures if t.format)
        if formats:
            lines.append("### Format Distribution")
            lines.append("")
            for fmt, count in formats.most_common(10):
                lines.append(f"- {fmt}: {count}")
            lines.append("")
        
        # Complete list
        lines.append("### Complete Texture List")
        lines.append("")
        lines.append("<details>")
        lines.append("<summary>Click to expand full texture list</summary>")
        lines.append("")
        lines.append("| # | Name | Size | Format | Memory |")
        lines.append("|---|------|------|--------|--------|")
        
        sorted_textures = sorted(textures, key=lambda t: t.memory_size, reverse=True)
        for i, t in enumerate(sorted_textures, 1):
            name = (t.name[:25] + "...") if len(t.name) > 25 else t.name
            size = f"{t.width}x{t.height}"
            if t.depth > 1:
                size += f"x{t.depth}"
            mem_str = f"{t.memory_size/1024:.1f} KB" if t.memory_size < 1024*1024 else f"{t.memory_size/(1024*1024):.2f} MB"
            fmt = t.format[:15] if t.format else "-"
            lines.append(f"| {i} | {name} | {size} | {fmt} | {mem_str} |")
        
        lines.append("")
        lines.append("</details>")
        lines.append("")
        
        return lines
    
    def _md_render_state_analysis(self) -> List[str]:
        """Generate render state statistics section."""
        lines = ["## 🔧 Render State Analysis", ""]
        
        if not self.rdc_data.draws:
            lines.append("No render state data available.")
            lines.append("")
            return lines
        
        # Check if any draw has state info
        has_state = any(hasattr(d, 'state') and d.state for d in self.rdc_data.draws)
        if not has_state:
            lines.append("Render state tracking not enabled for this capture.")
            lines.append("")
            return lines
        
        total = len(self.rdc_data.draws)
        blend_enabled = sum(1 for d in self.rdc_data.draws 
                          if hasattr(d, 'state') and d.state and 
                          hasattr(d.state, 'blend') and d.state.blend and d.state.blend.enabled)
        depth_test = sum(1 for d in self.rdc_data.draws 
                        if hasattr(d, 'state') and d.state and 
                        hasattr(d.state, 'depth') and d.state.depth and d.state.depth.test_enabled)
        depth_write = sum(1 for d in self.rdc_data.draws 
                         if hasattr(d, 'state') and d.state and 
                         hasattr(d.state, 'depth') and d.state.depth and d.state.depth.write_enabled)
        cull_enabled = sum(1 for d in self.rdc_data.draws 
                          if hasattr(d, 'state') and d.state and 
                          hasattr(d.state, 'cull') and d.state.cull and d.state.cull.enabled)
        
        lines.append("### State Usage Statistics")
        lines.append("")
        lines.append("| State | Enabled | Percentage |")
        lines.append("|-------|---------|------------|")
        lines.append(f"| Blend | {blend_enabled} | {blend_enabled/total*100:.1f}% |")
        lines.append(f"| Depth Test | {depth_test} | {depth_test/total*100:.1f}% |")
        lines.append(f"| Depth Write | {depth_write} | {depth_write/total*100:.1f}% |")
        lines.append(f"| Cull Face | {cull_enabled} | {cull_enabled/total*100:.1f}% |")
        lines.append("")
        
        return lines
    
    def _md_framebuffer_analysis(self) -> List[str]:
        """Generate framebuffer analysis section."""
        lines = ["## 🖥️ Framebuffer Configuration", ""]
        
        framebuffers = getattr(self.rdc_data, 'framebuffers', {})
        if not framebuffers:
            lines.append("No framebuffer data available.")
            lines.append("")
            return lines
        
        lines.append(f"**Total FBOs**: {len(framebuffers)}")
        lines.append("")
        
        lines.append("| FBO ID | Name | Color Attachments | Depth | Stencil |")
        lines.append("|--------|------|-------------------|-------|---------|")
        
        for fbo_id, fbo in framebuffers.items():
            color_count = len(fbo.color_attachments) if hasattr(fbo, 'color_attachments') else 0
            has_depth = "✓" if (hasattr(fbo, 'depth_attachment') and fbo.depth_attachment) or \
                              (hasattr(fbo, 'depth_stencil_attachment') and fbo.depth_stencil_attachment) else "-"
            has_stencil = "✓" if (hasattr(fbo, 'stencil_attachment') and fbo.stencil_attachment) or \
                                (hasattr(fbo, 'depth_stencil_attachment') and fbo.depth_stencil_attachment) else "-"
            name = fbo.name[:25] if hasattr(fbo, 'name') and fbo.name else "-"
            fbo_id_short = str(fbo_id)[:10]
            lines.append(f"| {fbo_id_short} | {name} | {color_count} | {has_depth} | {has_stencil} |")
        
        lines.append("")
        return lines
    
    def _md_dependency_analysis(self) -> List[str]:
        """Generate pass dependency analysis section."""
        lines = ["## 🔗 Pass Dependencies", ""]
        
        dependencies = getattr(self.rdc_data, 'pass_dependencies', [])
        if not dependencies:
            lines.append("No pass dependencies detected.")
            lines.append("")
            return lines
        
        lines.append(f"**Total Dependencies**: {len(dependencies)}")
        lines.append("")
        
        lines.append("| Source Pass | → | Target Pass | Resource Type |")
        lines.append("|-------------|---|-------------|---------------|")
        
        for dep in dependencies[:50]:  # Limit to 50 for readability
            src = dep.source_pass[:20] if hasattr(dep, 'source_pass') else "-"
            tgt = dep.target_pass[:20] if hasattr(dep, 'target_pass') else "-"
            res_type = dep.resource_type if hasattr(dep, 'resource_type') else "-"
            lines.append(f"| {src} | → | {tgt} | {res_type} |")
        
        if len(dependencies) > 50:
            lines.append(f"| ... | ... | ... | ({len(dependencies) - 50} more) |")
        
        lines.append("")
        return lines
    
    def _md_footer(self) -> List[str]:
        """Generate Markdown footer."""
        return [
            "---",
            "",
            "*Report generated by RenderDoc MCP Analyzer v2.0*",
            ""
        ]
    
    def save_all(self, output_path: Path) -> Dict[str, Path]:
        """Save both JSON and Markdown reports.
        
        Args:
            output_path: Directory to save reports
            
        Returns:
            Dictionary with 'json' and 'markdown' keys containing file paths
        """
        return {
            "json": self.save_json(output_path),
            "markdown": self.save_markdown(output_path)
        }
