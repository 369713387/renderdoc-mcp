# rd_mcp/tests/test_shader_detector.py
import pytest
from rd_mcp.detectors.shader import ShaderDetector
from rd_mcp.models import Issue, IssueSeverity

def test_detect_expensive_shaders():
    detector = ShaderDetector(threshold={"expensive_shader_instructions": 500})
    shaders = {
        "vs_main": {"instructions": 200},
        "ps_main": {"instructions": 600},  # Over threshold
        "cs_compute": {"instructions": 300}
    }
    issues = detector.detect_expensive_shaders(shaders)
    assert len(issues) == 1
    assert issues[0].type == "expensive_shader"
    assert "ps_main" in issues[0].description

def test_no_issue_when_under_threshold():
    detector = ShaderDetector(threshold={"expensive_shader_instructions": 1000})
    shaders = {
        "vs_main": {"instructions": 200},
        "ps_main": {"instructions": 600},
        "cs_compute": {"instructions": 300}
    }
    issues = detector.detect_expensive_shaders(shaders)
    assert len(issues) == 0

def test_multiple_expensive_shaders():
    detector = ShaderDetector(threshold={"expensive_shader_instructions": 300})
    shaders = {
        "vs_main": {"instructions": 400},
        "ps_main": {"instructions": 600},
        "cs_compute": {"instructions": 200}
    }
    issues = detector.detect_expensive_shaders(shaders)
    assert len(issues) == 2
    assert issues[0].type == "expensive_shader"
    assert issues[0].severity == IssueSeverity.WARNING

def test_default_threshold():
    detector = ShaderDetector(threshold={})
    shaders = {
        "ps_main": {"instructions": 600}  # Default threshold is 500
    }
    issues = detector.detect_expensive_shaders(shaders)
    assert len(issues) == 1

def test_shader_without_instructions_key():
    detector = ShaderDetector(threshold={"expensive_shader_instructions": 500})
    shaders = {
        "vs_main": {"other_data": 100},
        "ps_main": {"instructions": 600}
    }
    issues = detector.detect_expensive_shaders(shaders)
    assert len(issues) == 1
    assert "ps_main" in issues[0].description
