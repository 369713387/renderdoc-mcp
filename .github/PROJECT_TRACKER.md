# Project Tracker - Direct RDC Analysis Feature

## Overview
This document tracks the implementation of direct .rdc file analysis for the RenderDoc MCP server.

---

## 🎯 Feature #1: Direct RDC Analysis

**Status:** ✅ **Completed** (renderdoccmd-based approach)

### Summary
Implement direct analysis of RenderDoc capture files (.rdc) using renderdoccmd XML conversion.

### Background

**Previous workflow:**
```
.rdc file → rd.py → HTML report → html_parser → Analyzer → Results
```

**New workflow:**
```
.rdc file → renderdoccmd → XML → rdc_analyzer_cmd → Analyzer → Results
```

### Implementation Details

#### New Module: `rdc_analyzer_cmd.py`
- Uses `renderdoccmd convert` to convert .rdc to XML
- Parses XML to extract draw calls, shaders, textures, and performance metrics
- Groups draw calls into render passes
- **Works with any Python version** (no 3.6 dependency!)

#### Why renderdoccmd instead of Python API?

| Aspect | Python API (`rdc_analyzer.py`) | renderdoccmd (`rdc_analyzer_cmd.py`) |
|--------|--------------------------------|-------------------------------------|
| Python Version | ❌ Requires 3.6 | ✅ Any version |
| Installation | ❌ Complex | ✅ Simple |
| Compatibility | ❌ Limited | ✅ Universal |
| Maintenance | ❌ Difficult | ✅ Easy |

#### New MCP Tool: `analyze_rdc`
- Analyzes .rdc files directly
- Returns comprehensive analysis with issues categorized by severity
- Shows slowest passes and top draw calls by GPU time

#### Key Classes
- `RDCAnalyzerCMD` - Main analyzer class
- `RDCAnalysisData` - Complete analysis result
- `DrawCallInfo` - Draw call with timing
- `ShaderInfo` - Shader with source code
- `TextureInfo` - Texture resource
- `PassInfo` - Render pass

### Checklist

- [x] Create `rdc_analyzer.py` module (attempted, incompatible)
- [x] Create `rdc_analyzer_cmd.py` module (460+ lines)
- [x] Add `analyze_rdc` MCP tool to server
- [x] Add unit tests (11 passed)
- [x] Test with real RDC file (小米15_激烈战斗截帧1.rdc)
- [ ] Integration testing (see #2)
- [ ] Documentation updates (see #3)

### Files Changed

#### New Files
- `rd_mcp/rdc_analyzer.py` - Original attempt (Python API, incompatible)
- `rd_mcp/rdc_analyzer_cmd.py` - **Current implementation** (renderdoccmd)
- `rd_mcp/tests/test_rdc_analyzer.py` - Unit tests

#### Modified Files
- `rd_mcp/server.py` - Added `analyze_rdc` tool
- `rd_mcp/requirements.txt` - Added RenderDoc dependency note

### Usage

```python
from rd_mcp.rdc_analyzer_cmd import analyze_rdc_file

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

### Test Results

Successfully analyzed real RDC file (`小米15_激烈战斗截帧1.rdc`):

| Metric | Value |
|--------|-------|
| API | OpenGL ES 3.2 |
| GPU | Adreno 830 |
| Resolution | 2048x920 |
| Draw Calls | 922 |
| Shaders | 332 (163 VS + 163 FS + 6 CS) |
| Textures | 95 |
| Passes | 10 |

**Performance Analysis:** ✅ No issues found

---

## 🧪 Feature #2: Integration Testing

**Status:** ⏳ **Pending**

### Summary
Add integration tests for the direct RDC analysis feature using real .rdc capture files.

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
- [ ] Test with different API types
- [ ] Test with large number of draw calls
- [ ] Test performance with large files

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
- [ ] Add docstring examples to `rdc_analyzer_cmd.py`
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

- GitHub Issues are now enabled (previously disabled)
- Issue #1: Direct RDC Analysis (Completed)
- Issue #2: Integration Testing (Pending)
- Issue #3: Documentation Updates (Pending)

### Commits
- `db49a65` - feat: add direct RDC file analysis feature (initial)
- `f48f8d4` - feat: add renderdoccmd-based RDC analyzer (final)
