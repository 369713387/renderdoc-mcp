# rd_mcp/tests/test_full_analysis.py
"""Full integration test for RDC analysis with report generation."""
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from rd_mcp.rdc_analyzer_cmd import analyze_rdc_file, analyze_rdc_with_mali
from rd_mcp.analyzer import Analyzer
from rd_mcp.report_generator import ReportGenerator
from rd_mcp.models import ReportSummary
from rd_mcp.rdc_analyzer_cmd import PassInfo


def test_full_analysis(rdc_path: str, output_dir: str, mali_enabled: bool = True, mali_target_gpu: str = "Mali-G720"):
    """Run full analysis and generate reports.
    
    Args:
        rdc_path: Path to .rdc file
        output_dir: Directory to save reports
        mali_enabled: Whether to enable Mali shader analysis
        mali_target_gpu: Target Mali GPU
    """
    print(f"=== RDC Analysis Test ===")
    print(f"Input: {rdc_path}")
    print(f"Output: {output_dir}")
    print(f"Mali Enabled: {mali_enabled}")
    print(f"Mali GPU: {mali_target_gpu}")
    print()
    
    # Step 1: Analyze RDC file
    print("[1/4] Analyzing RDC file...")
    if mali_enabled:
        rdc_data, mali_result = analyze_rdc_with_mali(
            rdc_path,
            mali_enabled=True,
            mali_target_gpu=mali_target_gpu
        )
        print(f"  - Mali analysis: {mali_result.total_shaders_analyzed} shaders analyzed")
    else:
        rdc_data = analyze_rdc_file(rdc_path)
        mali_result = None
    
    print(f"  - Draw Calls: {rdc_data.summary.total_draw_calls}")
    print(f"  - Shaders: {len(rdc_data.shaders)}")
    print(f"  - Textures: {len(rdc_data.textures)}")
    print(f"  - Passes: {len(rdc_data.passes)}")
    print()
    
    # Step 2: Run analyzer
    print("[2/4] Running performance analysis...")
    analyzer = Analyzer(preset="mobile-balanced")
    
    summary = ReportSummary(
        api_type=rdc_data.summary.api_type,
        total_draw_calls=rdc_data.summary.total_draw_calls,
        total_shaders=rdc_data.summary.total_shaders,
        frame_count=rdc_data.summary.frame_count
    )
    
    shaders = {
        name: {
            "instruction_count": getattr(shader, 'instruction_count', 0),
            "stage": getattr(shader, 'stage', 'Unknown'),
            "binding_count": getattr(shader, 'binding_count', 0),
            "source": getattr(shader, 'source', None)
        }
        for name, shader in rdc_data.shaders.items()
    }
    
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
    
    passes = [
        PassInfo(
            name=pass_info.name,
            duration_ms=pass_info.duration_ms,
            resolution=pass_info.resolution
        )
        for pass_info in rdc_data.passes
    ]
    
    draws_list = rdc_data.draws if hasattr(rdc_data, 'draws') else None
    result = analyzer.analyze(summary, shaders, resources, draws_list, passes)
    
    print(f"  - Issues found: {result.metrics.get('total_issues', 0)}")
    print(f"  - Critical: {len(result.issues.get('critical', []))}")
    print(f"  - Warnings: {len(result.issues.get('warnings', []))}")
    print(f"  - Suggestions: {len(result.issues.get('suggestions', []))}")
    print()
    
    # Step 3: Generate reports
    print("[3/4] Generating reports...")
    generator = ReportGenerator(rdc_path, result, rdc_data, mali_result)
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    report_files = generator.save_all(output_path)
    
    print(f"  - JSON: {report_files['json']}")
    print(f"  - Markdown: {report_files['markdown']}")
    print()
    
    # Step 4: Verify reports
    print("[4/4] Verifying reports...")
    
    json_path = Path(report_files['json'])
    md_path = Path(report_files['markdown'])
    
    assert json_path.exists(), f"JSON report not found: {json_path}"
    assert md_path.exists(), f"Markdown report not found: {md_path}"
    
    json_size = json_path.stat().st_size
    md_size = md_path.stat().st_size
    
    print(f"  - JSON size: {json_size:,} bytes")
    print(f"  - Markdown size: {md_size:,} bytes")
    
    # Quick content validation
    import json as json_lib
    with open(json_path, 'r', encoding='utf-8') as f:
        json_data = json_lib.load(f)
    
    # Verify key sections exist
    assert 'summary' in json_data, "Missing 'summary' in JSON"
    assert 'shaders' in json_data, "Missing 'shaders' in JSON"
    assert 'textures' in json_data, "Missing 'textures' in JSON"
    assert 'draw_calls' in json_data, "Missing 'draw_calls' in JSON"
    assert 'passes' in json_data, "Missing 'passes' in JSON"
    assert 'issues' in json_data, "Missing 'issues' in JSON"
    
    if mali_enabled:
        assert 'mali_analysis' in json_data, "Missing 'mali_analysis' in JSON"
    
    print("  - JSON structure: ✓ Valid")
    
    with open(md_path, 'r', encoding='utf-8') as f:
        md_content = f.read()
    
    # Verify key sections in Markdown
    assert '# RenderDoc Performance Analysis Report' in md_content, "Missing header in Markdown"
    assert '## Executive Summary' in md_content or '## 执行摘要' in md_content, "Missing summary in Markdown"
    assert '## Shader Analysis' in md_content or '## Shader 分析' in md_content, "Missing shader section in Markdown"
    
    print("  - Markdown structure: ✓ Valid")
    print()
    
    print("=== Test PASSED ===")
    print(f"Reports generated at: {output_path}")
    
    return True


if __name__ == "__main__":
    # Default test paths
    rdc_file = r"D:\GitHubProject\renderdoc_mcp\小米15_激烈战斗截帧1.rdc"
    output_dir = r"D:\GitHubProject\renderdoc_mcp\test_output"
    
    # Allow command line override
    if len(sys.argv) > 1:
        rdc_file = sys.argv[1]
    if len(sys.argv) > 2:
        output_dir = sys.argv[2]
    
    try:
        test_full_analysis(rdc_file, output_dir, mali_enabled=True, mali_target_gpu="Mali-G720")
    except Exception as e:
        print(f"\n=== Test FAILED ===")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
