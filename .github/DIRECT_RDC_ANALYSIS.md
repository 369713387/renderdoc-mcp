# Direct RDC Analysis Feature

## Overview
This issue tracks the implementation of direct .rdc file analysis, bypassing the HTML report generation step for improved efficiency and simpler workflow.

## Background

**Previous workflow:**
```
.rdc file → rd.py → HTML report → html_parser → Analyzer → Results
```

**New workflow:**
```
.rdc file → rdc_analyzer → Analyzer → Results
```

## Implementation Plan

- [x] Create `rdc_analyzer.py` module with RenderDoc Python API integration
- [x] Add `analyze_rdc` MCP tool to server
- [x] Add unit tests for RDC analyzer
- [ ] Integration testing with actual .rdc files
- [ ] Update documentation
- [ ] Add error handling for edge cases

## Files Changed

### New Files
- `rd_mcp/rdc_analyzer.py` - Core RDC analysis module
- `rd_mcp/tests/test_rdc_analyzer.py` - Unit tests

### Modified Files
- `rd_mcp/server.py` - Added `analyze_rdc` tool
- `rd_mcp/requirements.txt` - Added RenderDoc dependency note

## Technical Details

### Key Classes
- `RDCAnalyzer` - Main analyzer class
- `RDCAnalysisData` - Complete analysis result container
- `DrawCallInfo` - Draw call information
- `ShaderInfo` - Shader information
- `TextureInfo` - Texture resource information
- `PassInfo` - Render pass information

### Dependencies
- RenderDoc Python API (installed via RenderDoc, not pip)

## Usage Example

```python
from rd_mcp.rdc_analyzer import analyze_rdc_file

data = analyze_rdc_file("capture.rdc")
print(f"API: {data.summary.api_type}")
print(f"Draws: {data.summary.total_draw_calls}")
print(f"Shaders: {data.summary.total_shaders}")
```

## Testing

- [x] Unit tests (11 passed)
- [ ] Integration tests with real .rdc files
- [ ] Performance benchmarks

## References
- Issue #2 - Integration testing
- Issue #3 - Documentation updates
