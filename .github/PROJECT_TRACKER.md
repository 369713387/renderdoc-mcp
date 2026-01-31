# Project Tracker - Direct RDC Analysis Feature

## Overview
This document tracks the implementation of direct .rdc file analysis for the RenderDoc MCP server.

---

## 🎯 Feature #1: Direct RDC Analysis

**Status:** ✅ **Completed**

### Summary
Implement direct analysis of RenderDoc capture files (.rdc) without generating intermediate HTML reports.

### Background

**Previous workflow:**
```
.rdc file → rd.py → HTML report → html_parser → Analyzer → Results
```

**New workflow:**
```
.rdc file → rdc_analyzer → Analyzer → Results
```

### Implementation Details

#### New Module: `rdc_analyzer.py`
- Uses RenderDoc Python API directly
- Extracts draw calls, shaders, textures, and performance metrics
- Groups draw calls into render passes
- Handles multiple graphics APIs (OpenGL, Vulkan, DirectX)

#### New MCP Tool: `analyze_rdc`
- Analyzes .rdc files directly
- Returns comprehensive analysis with issues categorized by severity
- Shows slowest passes and top draw calls by GPU time

#### Key Classes
- `RDCAnalyzer` - Main analyzer class
- `RDCAnalysisData` - Complete analysis result
- `DrawCallInfo` - Draw call information with GPU timing
- `ShaderInfo` - Shader information with instruction counts
- `TextureInfo` - Texture resource information
- `PassInfo` - Render pass with timing

### Checklist

- [x] Create `rdc_analyzer.py` module (400+ lines)
- [x] Add `analyze_rdc` MCP tool to server
- [x] Add unit tests (11 passed)
- [ ] Integration testing (see #2)
- [ ] Documentation updates (see #3)

### Files Changed

#### New Files
- `rd_mcp/rdc_analyzer.py`
- `rd_mcp/tests/test_rdc_analyzer.py`

#### Modified Files
- `rd_mcp/server.py` - Added `analyze_rdc` tool
- `rd_mcp/requirements.txt` - Added RenderDoc dependency note

### Usage

```python
from rd_mcp.rdc_analyzer import analyze_rdc_file

data = analyze_rdc_file("capture.rdc")
print(f"API: {data.summary.api_type}")
print(f"Draws: {data.summary.total_draw_calls}")
print(f"Shaders: {data.summary.total_shaders}")
```

### MCP Tool Usage

```json
{
  "tool": "analyze_rdc",
  "arguments": {
    "rdc_path": "D:/captures/scene1.rdc"
  }
}
```

---

## 🧪 Feature #2: Integration Testing

**Status:** ⏳ **Pending**

### Summary
Add integration tests for the direct RDC analysis feature using real .rdc capture files.

### Background
The `rdc_analyzer` module has unit tests, but we need integration tests with actual RenderDoc capture files.

### Tasks

#### Test Files
- [ ] Create test fixture directory structure
- [ ] Add sample .rdc files (small captures)
  - [ ] OpenGL capture
  - [ ] Vulkan capture
  - [ ] DirectX capture (if available)
- [ ] Add expected output data for each test

#### Test Cases
- [ ] Test with valid .rdc file
- [ ] Test with corrupted .rdc file
- [ ] Test with file missing GPU counters
- [ ] Test with different API types
- [ ] Test with large number of draw calls
- [ ] Test performance with large files

#### Test File Structure
```
rd_mcp/tests/fixtures/
├── captures/
│   ├── simple_opengl.rdc
│   ├── simple_vulkan.rdc
│   └── expected/
│       ├── simple_opengl.json
│       └── simple_vulkan.json
└── README.md
```

---

## 📚 Feature #3: Documentation Updates

**Status:** ⏳ **Pending**

### Summary
Update project documentation to include the new direct RDC analysis feature.

### Tasks

#### README Updates
- [ ] Add `analyze_rdc` tool to main feature list
- [ ] Update workflow diagram
- [ ] Add usage examples
- [ ] Update installation requirements

#### MCP_CONFIG.md Updates
- [ ] Document `analyze_rdc` tool parameters
- [ ] Add usage examples
- [ ] Update troubleshooting section

#### API Documentation
- [ ] Add docstring examples to `rdc_analyzer.py`
- [ ] Create API reference for new classes
- [ ] Add type hints documentation

#### Guides
- [ ] Create "Getting Started" guide for direct RDC analysis
- [ ] Add migration guide from HTML workflow
- [ ] Create troubleshooting guide

---

## 📊 Progress Summary

| Feature | Status | Progress |
|---------|--------|----------|
| #1 Direct RDC Analysis | ✅ Completed | 100% |
| #2 Integration Testing | ⏳ Pending | 0% |
| #3 Documentation Updates | ⏳ Pending | 0% |

**Overall Progress:** 33% (1/3 completed)

---

## 🔗 References

- [CLAUDE.md](../CLAUDE.md) - Project instructions
- [MCP_CONFIG.md](../rd_mcp/MCP_CONFIG.md) - MCP configuration guide
- [DIRECT_RDC_ANALYSIS.md](./DIRECT_RDC_ANALYSIS.md) - Technical details

---

## 📝 Notes

- All GitHub Issues are disabled in this repository
- Use this file for project tracking instead
- Update this file as tasks progress
