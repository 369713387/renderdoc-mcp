import pytest
from rd_mcp.detectors.base import BaseDetector
from rd_mcp.models import Issue, IssueSeverity

class MockDetector(BaseDetector):
    @property
    def name(self) -> str:
        return "mock_detector"

    def detect(self, data):
        return [
            Issue(
                type="test_issue",
                severity=IssueSeverity.CRITICAL,
                description="Test",
                location="Test",
                impact="high"
            )
        ]

def test_base_detector_interface():
    """Test base detector interface"""
    detector = MockDetector(thresholds={"max": 100})
    assert detector.name == "mock_detector"

    issues = detector.detect(None)
    assert len(issues) == 1
    assert issues[0].type == "test_issue"
