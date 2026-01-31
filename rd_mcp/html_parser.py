# rd_mcp/html_parser.py
from pathlib import Path
from bs4 import BeautifulSoup
from rd_mcp.models import ReportSummary
import re

class HTMLParser:
    """Parser for RenderDoc HTML reports.

    This class parses RenderDoc HTML capture reports and extracts
    summary information such as API type, draw calls, shaders, and frame count.
    """

    def __init__(self, report_path: str):
        """Initialize the HTML parser with a report directory path.

        Args:
            report_path: Path to the RenderDoc HTML report directory

        Raises:
            FileNotFoundError: If the report directory does not exist
            ValueError: If the path is not a directory
        """
        self.report_path = Path(report_path).resolve()
        # Validate path exists and is a directory
        if not self.report_path.exists():
            raise FileNotFoundError(f"Report directory not found: {report_path}")
        if not self.report_path.is_dir():
            raise ValueError(f"Path must be a directory: {report_path}")
        self.soup = None

    def _load_html(self):
        """Load the HTML report file into memory.

        Raises:
            FileNotFoundError: If index.html is not found in the report directory
            ValueError: If the HTML file has encoding errors
        """
        if self.soup is None:
            html_path = self.report_path / "index.html"
            if not html_path.exists():
                raise FileNotFoundError(f"HTML report not found: {html_path}")

            try:
                content = html_path.read_text(encoding="utf-8")
            except UnicodeDecodeError as e:
                raise ValueError(f"HTML file encoding error. Expected UTF-8: {e}")

            self.soup = BeautifulSoup(content, "lxml")

    def extract_summary(self) -> ReportSummary:
        """Extract summary information from the HTML report.

        Parses the HTML report to extract key metrics including API type,
        number of draw calls, shader count, and frame count.

        Returns:
            ReportSummary: Summary containing API type, draw calls, shaders, frames

        Raises:
            FileNotFoundError: If the HTML report file is not found
            ValueError: If the HTML file has encoding errors
        """
        self._load_html()

        # Extract API type from title or heading
        api_type = "Unknown"

        # Check title first
        title = self.soup.find("title")
        if title:
            text = title.get_text()
            # Prioritize more specific APIs first
            for api in ["OpenGL ES", "Vulkan", "DirectX", "Direct3D", "Metal", "OpenGL"]:
                if api in text:
                    api_type = api
                    break

        # Extract metrics - look for common patterns in RenderDoc reports
        body = self.soup.get_text()

        # If not found in title, check body content
        if api_type == "Unknown":
            # Prioritize more specific APIs first
            for api in ["OpenGL ES", "Vulkan", "DirectX", "Direct3D", "Metal", "OpenGL"]:
                if api in body:
                    api_type = api
                    break

        # Try to find draw call count (be specific about "Draw Calls" first)
        draw_match = re.search(r'<p><strong>Draw Calls:</strong>\s*([\d,]+)</p>', body, re.IGNORECASE)
        if not draw_match:
            # Look for "Draw Calls:" text before the number
            draw_match = re.search(r'Draw Calls:\s*([\d,]+)', body, re.IGNORECASE)
        if not draw_match:
            # Fallback to generic pattern
            draw_match = re.search(r'([\d,]+)\s*(?:draw calls?|draws?)', body, re.IGNORECASE)
        if draw_match:
            total_draw_calls = int(draw_match.group(1).replace(',', '')) if draw_match.group(1) else 0
        else:
            total_draw_calls = 0

        # Try to find shader count (be specific about "Shaders" first)
        shader_match = re.search(r'<p><strong>Shaders:</strong>\s*([\d,]+)</p>', body, re.IGNORECASE)
        if not shader_match:
            # Look for "Shaders:" text before the number
            shader_match = re.search(r'Shaders:\s*([\d,]+)', body, re.IGNORECASE)
        if not shader_match:
            # Fallback to generic pattern
            shader_match = re.search(r'([\d,]+)\s*shaders?', body, re.IGNORECASE)
        if shader_match:
            total_shaders = int(shader_match.group(1).replace(',', '')) if shader_match.group(1) else 0
        else:
            total_shaders = 0

        # Assume single frame for now
        frame_count = 1

        return ReportSummary(
            api_type=api_type,
            total_draw_calls=total_draw_calls,
            total_shaders=total_shaders,
            frame_count=frame_count
        )
