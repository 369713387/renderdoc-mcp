# rd_mcp/html_parser.py
from pathlib import Path
from bs4 import BeautifulSoup
from rd_mcp.models import ReportSummary
import re

class HTMLParser:
    def __init__(self, report_path: str):
        self.report_path = Path(report_path)
        self.soup = None

    def _load_html(self):
        if self.soup is None:
            html_path = self.report_path / "index.html"
            if not html_path.exists():
                raise FileNotFoundError(f"HTML report not found: {html_path}")
            self.soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "lxml")

    def extract_summary(self) -> ReportSummary:
        self._load_html()

        # Extract API type from title or heading
        api_type = "Unknown"
        title = self.soup.find("title")
        if title:
            text = title.get_text()
            for api in ["OpenGL", "Vulkan", "DirectX", "Direct3D", "Metal"]:
                if api in text:
                    api_type = api
                    break

        # Extract metrics - look for common patterns in RenderDoc reports
        body = self.soup.get_text()

        # Try to find draw call count
        draw_match = re.search(r'(\d+)\s*(?:draw calls?|draws?)', body, re.IGNORECASE)
        total_draw_calls = int(draw_match.group(1)) if draw_match else 0

        # Try to find shader count
        shader_match = re.search(r'(\d+)\s*shaders?', body, re.IGNORECASE)
        total_shaders = int(shader_match.group(1)) if shader_match else 0

        # Assume single frame for now
        frame_count = 1

        return ReportSummary(
            api_type=api_type,
            total_draw_calls=total_draw_calls,
            total_shaders=total_shaders,
            frame_count=frame_count
        )
