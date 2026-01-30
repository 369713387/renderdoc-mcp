# rd_mcp/tests/test_html_parser.py
import pytest
from pathlib import Path
from rd_mcp.html_parser import HTMLParser
from rd_mcp.models import ReportSummary

def test_extract_summary_from_valid_html():
    # Create a minimal valid HTML fixture
    html_content = """
    <!DOCTYPE html>
    <html>
    <head><title>OpenGL Test Report</title></head>
    <body>
        <h1>API: OpenGL</h1>
        <div class="draw-calls">100 draw calls</div>
        <div class="shaders">5 shaders</div>
        <div class="frames">1 frame</div>
    </body>
    </html>
    """
    fixture_path = Path(__file__).parent / "fixtures" / "index.html"
    fixture_path.parent.mkdir(parents=True, exist_ok=True)
    fixture_path.write_text(html_content)

    parser = HTMLParser(str(fixture_path.parent))
    summary = parser.extract_summary()

    assert summary.api_type == "OpenGL"
    assert summary.total_draw_calls == 100
    assert summary.total_shaders == 5
    assert summary.frame_count == 1
