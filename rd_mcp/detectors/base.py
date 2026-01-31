from abc import ABC, abstractmethod
from typing import Any, Dict, List
from rd_mcp.models import Issue

class BaseDetector(ABC):
    """Base class for all performance detectors."""

    def __init__(self, thresholds: Dict[str, Any]):
        """Initialize detector with thresholds.

        Args:
            thresholds: Dictionary of threshold values for detection
        """
        self.thresholds = thresholds

    @abstractmethod
    def detect(self, data: Any) -> List[Issue]:
        """Execute detection and return list of issues.

        Args:
            data: Input data for detection (type varies by detector)

        Returns:
            List of Issue objects found
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Get detector name.

        Returns:
            Detector name string
        """
        pass
