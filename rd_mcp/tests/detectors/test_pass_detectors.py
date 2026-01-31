import pytest
from rd_mcp.detectors.passes.duration import PassDurationDetector
from rd_mcp.detectors.passes.switches import PassSwitchesDetector
from rd_mcp.models import IssueSeverity

def test_slow_pass_detection():
    """Test detection of slow render passes"""
    detector = PassDurationDetector({
        "max_duration_ms": 0.5
    })

    passes = _create_mock_passes([
        ("Geometry", 0.3),
        ("Shadow", 5.2),  # Too slow
        ("Transparent", 0.4)
    ])

    issues = detector.detect(passes)

    assert len(issues) == 1
    assert issues[0].type == "slow_pass"
    assert "Shadow" in issues[0].location
    assert "5.2" in issues[0].description

def test_normal_pass_durations():
    """Test that normal pass durations don't trigger detection"""
    detector = PassDurationDetector({
        "max_duration_ms": 1.0
    })

    passes = _create_mock_passes([
        ("Geometry", 0.3),
        ("Shadow", 0.8),
        ("Transparent", 0.4)
    ])

    issues = detector.detect(passes)

    assert len(issues) == 0

def test_pass_switches_detection():
    """Test detection of excessive pass switches"""
    detector = PassSwitchesDetector({
        "max_switches_per_frame": 10
    })

    draws = _create_mock_draws_with_switches(15)  # 15 marker switches
    issues = detector.detect(draws)

    assert len(issues) == 1
    assert issues[0].type == "pass_switches"
    assert "15" in issues[0].description

def test_normal_pass_switches():
    """Test that normal pass switches don't trigger detection"""
    detector = PassSwitchesDetector({
        "max_switches_per_frame": 20
    })

    draws = _create_mock_draws_with_switches(5)  # Only 5 switches
    issues = detector.detect(draws)

    assert len(issues) == 0

def test_pass_switch_info_extraction():
    """Test detailed switch information"""
    detector = PassSwitchesDetector({})

    draws = _create_mock_draws_with_switches(5)
    info = detector.extract_switch_info(draws)

    assert info.marker_switches == 5
    assert info.total > 0

def test_detector_name():
    """Test detector name property"""
    duration_detector = PassDurationDetector({})
    switches_detector = PassSwitchesDetector({})

    assert duration_detector.name == "pass_duration"
    assert switches_detector.name == "pass_switches"

def _create_mock_passes(duration_data):
    """Helper to create mock passes"""
    from rd_mcp.rdc_analyzer_cmd import PassInfo, DrawCallInfo
    passes = []
    for name, duration in duration_data:
        pass_info = PassInfo(
            name=name,
            draw_calls=[DrawCallInfo(draw_id=1, event_id=1, name="draw")],
            duration_ms=duration,
            resolution="1920x1080"
        )
        passes.append(pass_info)
    return passes

def _create_mock_draws_with_switches(num_switches):
    """Helper to create draws with marker switches"""
    from rd_mcp.rdc_analyzer_cmd import DrawCallInfo
    draws = []
    for i in range(num_switches * 2):
        draws.append(DrawCallInfo(
            draw_id=i,
            event_id=i,
            name="glDrawArrays",
            marker=f"Pass_{i // 2}"
        ))
    return draws
