# rd_mcp/tests/test_html_parser.py
import pytest
from pathlib import Path
from rd_mcp.html_parser import HTMLParser
from rd_mcp.models import ReportSummary


def test_extract_summary_from_valid_html(tmp_path):
    """Test extracting summary from a valid HTML report."""
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
    fixture_path = tmp_path / "index.html"
    fixture_path.write_text(html_content, encoding="utf-8")

    parser = HTMLParser(str(tmp_path))
    summary = parser.extract_summary()

    assert summary.api_type == "OpenGL"
    assert summary.total_draw_calls == 100
    assert summary.total_shaders == 5
    assert summary.frame_count == 1


def test_file_not_found_when_directory_doesnt_exist(tmp_path):
    """Test FileNotFoundError when report directory doesn't exist."""
    non_existent_path = tmp_path / "non_existent_dir"

    with pytest.raises(FileNotFoundError, match="Report directory not found"):
        HTMLParser(str(non_existent_path))


def test_value_error_when_path_is_not_directory(tmp_path):
    """Test ValueError when path is a file, not a directory."""
    file_path = tmp_path / "not_a_dir.html"
    file_path.write_text("<html></html>")

    with pytest.raises(ValueError, match="Path must be a directory"):
        HTMLParser(str(file_path))


def test_empty_html_file(tmp_path):
    """Test extracting summary from an empty HTML file."""
    fixture_path = tmp_path / "index.html"
    fixture_path.write_text("", encoding="utf-8")

    parser = HTMLParser(str(tmp_path))
    summary = parser.extract_summary()

    # Empty HTML should return default values
    assert summary.api_type == "Unknown"
    assert summary.total_draw_calls == 0
    assert summary.total_shaders == 0
    assert summary.frame_count == 1


def test_html_with_no_api_type(tmp_path):
    """Test extracting summary from HTML with no API type information."""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head><title>Graphics Report</title></head>
    <body>
        <div class="draw-calls">50 draw calls</div>
        <div class="shaders">3 shaders</div>
    </body>
    </html>
    """
    fixture_path = tmp_path / "index.html"
    fixture_path.write_text(html_content, encoding="utf-8")

    parser = HTMLParser(str(tmp_path))
    summary = parser.extract_summary()

    # Should default to "Unknown" when no API type is found
    assert summary.api_type == "Unknown"
    assert summary.total_draw_calls == 50
    assert summary.total_shaders == 3
    assert summary.frame_count == 1


def test_html_with_no_draw_calls_or_shaders(tmp_path):
    """Test extracting summary from HTML with no draw calls or shaders information."""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head><title>Vulkan Test Report</title></head>
    <body>
        <h1>API: Vulkan</h1>
        <div>Some other content</div>
    </body>
    </html>
    """
    fixture_path = tmp_path / "index.html"
    fixture_path.write_text(html_content, encoding="utf-8")

    parser = HTMLParser(str(tmp_path))
    summary = parser.extract_summary()

    # Should extract API type but return 0 for missing metrics
    assert summary.api_type == "Vulkan"
    assert summary.total_draw_calls == 0
    assert summary.total_shaders == 0
    assert summary.frame_count == 1


def test_file_not_found_when_index_html_missing(tmp_path):
    """Test FileNotFoundError when index.html is missing from report directory."""
    # Create directory but no index.html
    report_dir = tmp_path / "empty_report"
    report_dir.mkdir()

    parser = HTMLParser(str(report_dir))

    with pytest.raises(FileNotFoundError, match="HTML report not found"):
        parser.extract_summary()


def test_encoding_error_handling(tmp_path):
    """Test ValueError for HTML file with encoding errors."""
    fixture_path = tmp_path / "index.html"
    # Write invalid UTF-8 content
    fixture_path.write_bytes(b'\xff\xfe Invalid UTF-8 content')

    parser = HTMLParser(str(tmp_path))

    with pytest.raises(ValueError, match="HTML file encoding error"):
        parser.extract_summary()
