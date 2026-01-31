# RenderDoc MCP Server Presets

This document describes the available presets for the RenderDoc MCP Server. Presets provide pre-configured threshold values optimized for different development scenarios and hardware platforms.

## Overview

Presets allow you to quickly apply analysis configurations tailored to your specific needs. Instead of manually configuring each threshold, you can choose a preset that matches your target platform or optimization goals.

## Available Presets

### Mobile-Aggressive

**Purpose:** Strict performance optimization for mobile devices
**Target Platform:** Mobile phones, tablets, low-end hardware
**Use Case:** Optimizing for maximum performance on resource-constrained devices

**Thresholds:**
- **Geometry:**
  - Max Draw Calls: 500 (strict)
  - Max Triangles: 50,000
  - Max Triangles per Model: 10,000
- **Shader:**
  - Max Vertex Shader Instructions: 100
  - Max Fragment Shader Instructions: 150
  - Max Compute Shader Instructions: 200
- **Render Pass:**
  - Max Duration: 0.3ms (very strict)
  - Max Overdraw Ratio: 2.0
  - Max Switches per Frame: 8
- **Memory:**
  - Max Texture Size: 2048px
  - Require Compressed Textures: Yes

### Mobile-Balanced

**Purpose:** Balanced performance for mobile devices
**Target Platform:** Mid-range mobile devices, tablets
**Use Case:** General mobile development with reasonable performance targets

**Thresholds:**
- **Geometry:**
  - Max Draw Calls: 1000
  - Max Triangles: 100,000
  - Max Triangles per Model: 25,000
- **Shader:**
  - Max Vertex Shader Instructions: 300
  - Max Fragment Shader Instructions: 400
  - Max Compute Shader Instructions: 600
- **Render Pass:**
  - Max Duration: 0.5ms
  - Max Overdraw Ratio: 2.5
  - Max Switches per Frame: 15
- **Memory:**
  - Max Texture Size: 2048px
  - Require Compressed Textures: Yes

### PC-Balanced

**Purpose:** Balanced performance for desktop gaming
**Target Platform:** Mid-to-high end PC hardware
**Use Case:** General PC game development with performance awareness

**Thresholds:**
- **Geometry:**
  - Max Draw Calls: 2000
  - Max Triangles: 500,000
  - Max Triangles per Model: 100,000
- **Shader:**
  - Max Vertex Shader Instructions: 500
  - Max Fragment Shader Instructions: 500
  - Max Compute Shader Instructions: 1000
- **Render Pass:**
  - Max Duration: 1.0ms
  - Max Overdraw Ratio: 2.5
  - Max Switches per Frame: 20
- **Memory:**
  - Max Texture Size: 4096px
  - Require Compressed Textures: No (optional)

## Usage Examples

### Using Presets with MCP Tools

When analyzing a RenderDoc report, you can specify a preset to apply its configuration:

```bash
# Using preset in analysis
Analyze the report at D:/capture/report using preset mobile-aggressive

# Or with explicit parameter preset=mobile-aggressive
Analyze the report at D:/capture/report with preset mobile-balanced
```

### Overriding Preset Values

You can override specific threshold values while using a preset:

```bash
# Override max draw calls while using mobile-balanced preset
Analyze the report at D:/capture/report with preset mobile-balanced and override thresholds: {"geometry": {"max_draw_calls": 1500}}
```

### Programmatic Usage

```python
from rd_mcp.analyzer import Analyzer

# Use a preset directly
analyzer = Analyzer(preset='mobile-aggressive')
result = analyzer.analyze(...)

# Use preset with overrides
analyzer = Analyzer(preset='pc-balanced',
                   overrides={"geometry": {"max_draw_calls": 3000}})
```

## Preset Selection Guide

### When to Use Mobile-Aggressive

- Developing for entry-level mobile devices
- Targeting 60+ FPS on low-end hardware
- Memory-constrained environments
- Battery-optimized applications
- Games targeting devices with limited GPU capabilities

### When to Use Mobile-Balanced

- General mobile game development
- Targeting mainstream mobile devices
- Balancing visual quality with performance
- Applications with moderate complexity
- When you want reasonable performance without being overly strict

### When to Use PC-Balanced

- Desktop game development
- Mid-to-high end target hardware
- Visual quality-focused projects
- Mixed platform development
- When performance is important but not the absolute priority

## Custom Presets

You can create your own preset configurations by adding JSON files in the `rd_mcp/presets/` directory:

```json
{
  "description": "Custom optimization preset",
  "thresholds": {
    "geometry": {
      "max_draw_calls": 1500,
      "max_triangles": 300000,
      "max_triangles_per_model": 50000
    },
    "shader": {
      "max_vs_instructions": 400,
      "max_fs_instructions": 600,
      "max_cs_instructions": 800
    },
    "pass": {
      "max_duration_ms": 0.8,
      "max_overdraw_ratio": 3.0,
      "max_switches_per_frame": 25
    },
    "memory": {
      "max_texture_size": 4096,
      "require_compressed_textures": false
    }
  }
}
```

Save this as `custom-preset.json` in the presets directory and reference it as:
```
Analyze the report at D:/capture/report using preset custom-preset
```

## Troubleshooting

### Preset Not Found

If you receive an error that a preset is not found:

1. Verify the preset name is spelled correctly
2. Check that the preset file exists in `rd_mcp/presets/`
3. Ensure the JSON file is valid and properly formatted

### Threshold Override Not Applied

When overriding preset values:

- Override values must match the threshold category structure
- Ensure nested dictionaries are properly formatted
- Check that you're using the correct field names

### Performance Impact

- **Aggressive presets** will flag more issues, potentially leading to false positives
- **Balanced presets** provide a middle ground between strictness and practicality
- Always consider your target platform when choosing a preset

## Best Practices

1. **Start with balanced presets** and adjust based on your target hardware
2. **Use aggressive presets** for mobile optimization when targeting low-end devices
3. **Combine with custom overrides** to fine-tune analysis for specific needs
4. **Regularly review** preset thresholds as your project evolves
5. **Document your choice** when working in team environments

## Integration with Development Workflow

Presets can be integrated into your development workflow by:

1. Setting up project-specific presets in your version control
2. Using different presets for different build configurations
3. Automatically applying presets based on target platform during CI/CD
4. Gradually transitioning from strict to relaxed presets as hardware requirements evolve