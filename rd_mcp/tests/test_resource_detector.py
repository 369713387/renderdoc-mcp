# rd_mcp/tests/test_resource_detector.py
import pytest
from rd_mcp.detectors.resource import ResourceDetector
from rd_mcp.models import Issue, IssueSeverity

def test_detect_large_textures():
    detector = ResourceDetector(threshold={"large_texture_size": 4096})
    resources = [
        {"name": "albedo", "width": 1024, "height": 1024},
        {"name": "shadow_map", "width": 4096, "height": 4096},
        {"name": "env_map", "width": 8192, "height": 4096}
    ]
    issues = detector.detect_large_textures(resources)
    assert len(issues) >= 1

def test_no_issue_when_under_threshold():
    detector = ResourceDetector(threshold={"large_texture_size": 8192})
    resources = [
        {"name": "albedo", "width": 1024, "height": 1024},
        {"name": "shadow_map", "width": 4096, "height": 4096},
        {"name": "env_map", "width": 2048, "height": 2048}
    ]
    issues = detector.detect_large_textures(resources)
    assert len(issues) == 0

def test_multiple_large_textures():
    detector = ResourceDetector(threshold={"large_texture_size": 2048})
    resources = [
        {"name": "albedo", "width": 4096, "height": 1024},
        {"name": "shadow_map", "width": 4096, "height": 4096},
        {"name": "env_map", "width": 1024, "height": 1024}
    ]
    issues = detector.detect_large_textures(resources)
    assert len(issues) == 2
    assert issues[0].type == "large_texture"
    assert issues[0].severity == IssueSeverity.WARNING

def test_default_threshold():
    detector = ResourceDetector(threshold={})
    resources = [
        {"name": "env_map", "width": 8192, "height": 4096}  # Default threshold is 4096
    ]
    issues = detector.detect_large_textures(resources)
    assert len(issues) == 1

def test_texture_without_name():
    detector = ResourceDetector(threshold={"large_texture_size": 1024})
    resources = [
        {"width": 2048, "height": 1024}
    ]
    issues = detector.detect_large_textures(resources)
    assert len(issues) == 1
    assert "unknown" in issues[0].location

def test_texture_exceeds_threshold_by_width():
    detector = ResourceDetector(threshold={"large_texture_size": 1024})
    resources = [
        {"name": "wide_texture", "width": 2048, "height": 512}
    ]
    issues = detector.detect_large_textures(resources)
    assert len(issues) == 1
    assert "wide_texture" in issues[0].description

def test_texture_exceeds_threshold_by_height():
    detector = ResourceDetector(threshold={"large_texture_size": 1024})
    resources = [
        {"name": "tall_texture", "width": 512, "height": 2048}
    ]
    issues = detector.detect_large_textures(resources)
    assert len(issues) == 1
    assert "tall_texture" in issues[0].description

def test_texture_exactly_at_threshold():
    detector = ResourceDetector(threshold={"large_texture_size": 4096})
    resources = [
        {"name": "exact_texture", "width": 4096, "height": 4096}
    ]
    issues = detector.detect_large_textures(resources)
    assert len(issues) == 0
