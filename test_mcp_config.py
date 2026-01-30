#!/usr/bin/env python3
"""Test script to verify MCP server configuration.

This script helps verify that the MCP server is properly configured
and can be imported and run.
"""
import sys
import asyncio
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# ASCII-safe checkmarks for Windows console
CHECK = "[OK]"
CROSS = "[FAIL]"

def test_imports():
    """Test that all modules can be imported."""
    print("Testing imports...")
    try:
        import rd_mcp
        print(f"  {CHECK} rd_mcp imported (version {rd_mcp.__version__})")

        from rd_mcp.models import Issue, IssueSeverity, AnalysisResult, ReportSummary
        print("  {CHECK} Models imported")

        from rd_mcp.config import Config, Thresholds
        print("  {CHECK} Config imported")

        from rd_mcp.html_parser import HTMLParser
        print("  {CHECK} HTMLParser imported")

        from rd_mcp.detectors.drawcall import DrawCallDetector
        from rd_mcp.detectors.shader import ShaderDetector
        from rd_mcp.detectors.resource import ResourceDetector
        print("  {CHECK} Detectors imported")

        from rd_mcp.analyzer import Analyzer
        print("  {CHECK} Analyzer imported")

        from rd_mcp import server
        print("  {CHECK} MCP server module imported")

        return True
    except ImportError as e:
        print(f"  {CROSS} Import failed: {e}")
        return False

def test_config():
    """Test configuration loading."""
    print("\nTesting configuration...")
    try:
        from rd_mcp.config import Config

        config = Config.load()
        print(f"  {CHECK} Config loaded")
        print(f"    - max_draw_calls: {config.thresholds.max_draw_calls}")
        print(f"    - expensive_shader_instructions: {config.thresholds.expensive_shader_instructions}")
        print(f"    - large_texture_size: {config.thresholds.large_texture_size}")
        print(f"    - overdraw_threshold: {config.thresholds.overdraw_threshold}")
        return True
    except Exception as e:
        print(f"  {CROSS} Config loading failed: {e}")
        return False

def test_server_instance():
    """Test MCP server instantiation."""
    print("\nTesting MCP server...")
    try:
        from rd_mcp import server
        print(f"  {CHECK} Server created: {server.server.name}")
        print(f"  {CHECK} Server type: {type(server.server)}")
        return True
    except Exception as e:
        print(f"  {CROSS} Server test failed: {e}")
        return False

def test_models():
    """Test model creation and validation."""
    print("\nTesting models...")
    try:
        from rd_mcp.models import Issue, IssueSeverity

        issue = Issue(
            type="test",
            severity=IssueSeverity.CRITICAL,
            description="Test issue",
            location="Test location"
        )
        print(f"  {CHECK} Issue model works")
        print(f"    - Created issue: {issue.type}")

        # Test serialization
        json_str = issue.model_dump_json()
        print(f"  {CHECK} JSON serialization works")
        return True
    except Exception as e:
        print(f"  {CROSS} Model test failed: {e}")
        return False

def show_config_template():
    """Show MCP configuration template."""
    print("\n" + "=" * 70)
    print("MCP CONFIGURATION TEMPLATE")
    print("=" * 70)
    print("\nAdd this to your Claude Desktop config file:")
    print("\nWindows: %APPDATA%\\Claude\\claude_desktop_config.json")
    print("macOS:   ~/Library/Application Support/Claude/claude_desktop_config.json")
    print("Linux:   ~/.config/Claude/claude_desktop_config.json")
    print("\n" + "-" * 70)

    project_path = str(project_root).replace("\\", "\\\\")
    config = f"""{{
  "mcpServers": {{
    "renderdoc": {{
      "command": "python",
      "args": ["-m", "rd_mcp.server"],
      "cwd": "{project_path}"
    }}
  }}
}}"""
    print(config)
    print("-" * 70)
    print("\nThen restart Claude Desktop.")
    print("=" * 70)

def main():
    """Run all tests."""
    print("=" * 70)
    print("RenderDoc MCP Server Configuration Test")
    print("=" * 70)
    print(f"\nProject root: {project_root}")

    results = []
    results.append(("Imports", test_imports()))
    results.append(("Configuration", test_config()))
    results.append(("Models", test_models()))
    results.append(("Server", test_server_instance()))

    print("\n" + "=" * 70)
    print("TEST RESULTS")
    print("=" * 70)

    all_passed = True
    for name, passed in results:
        status = "[OK]" if passed else "[FAIL]"
        print(f"{name}: {status}")
        if not passed:
            all_passed = False

    print("=" * 70)

    if all_passed:
        print("\n[OK] All tests passed! MCP server is ready to use.")
        show_config_template()
    else:
        print("\n[FAIL] Some tests failed. Please check the errors above.")
        print("\nTroubleshooting:")
        print("1. Make sure you're in the project root directory")
        print("2. Install dependencies: pip install -r rd_mcp/requirements.txt")
        print("3. Check Python version: python --version (need 3.8+)")
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
