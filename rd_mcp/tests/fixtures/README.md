# Test Fixtures

This directory contains test fixtures and mock data used for integration testing of the RenderDoc MCP server.

## Directory Structure

```
fixtures/
├── index.html                    # Basic HTML report fixture
├── test_clean.html              # Clean report with no issues
└── README.md                    # This file
```

## Fixture Files

### `index.html`
Basic HTML report fixture for testing HTML parsing functionality.
- Contains minimal HTML structure
- Used as a baseline for parsing tests

### `test_clean.html`
Clean HTML report fixture for testing reports without performance issues.
- Contains optimized rendering data
- Used to verify clean detection logic

## Adding New Fixtures

When adding new fixtures, follow these guidelines:

1. **Naming Convention**: Use descriptive names that clearly indicate the test scenario
   - Use underscores for word separation
   - Include version or date if relevant (e.g., `mobile_game_v1.html`)

2. **File Organization**:
   - Group related fixtures in subdirectories if needed
   - Keep files under 1MB when possible
   - Compress large files if necessary

3. **Content Guidelines**:
   - Include realistic data that matches actual RenderDoc output
   - Use appropriate HTML structure with semantic tags
   - Include metadata and statistics that would appear in real reports
   - Add comments to explain specific test scenarios

4. **Example Structure**:
```html
<!DOCTYPE html>
<html>
<head>
    <title>RenderDoc Capture - [Scenario Name]</title>
    <!-- Add any required meta tags or styles -->
</head>
<body>
    <!-- Include realistic frame statistics -->
    <div class="frame-stats">
        <p>Total draw calls: [number]</p>
        <p>Shaders: [number]</p>
        <p>Frame time: [value]ms</p>
    </div>

    <!-- Include API information -->
    <div class="api-info">
        <p>API: [API type]</p>
        <p>Version: [version]</p>
    </div>
</body>
</html>
```

## Test Data Guidelines

### For Mobile Games
- Include high draw call counts (1000+)
- Include multiple shader variants
- Include large texture resources
- Include performance metrics specific to mobile

### For Desktop Games
- Include complex rendering pipelines
- Include advanced shader features
- Include multiple render passes
- Include detailed resource statistics

### For WebGL Content
- Include WebGL-specific API calls
- Include compressed texture formats
- Include mobile-specific constraints
- Include performance bottlenecks

## Mock Data Structure

When creating mock data for integration tests:

```python
mock_rdc_data = {
    "frame": {
        "draw_calls": [
            # Draw call data structure
        ],
        "shaders": {
            # Shader analysis data
        },
        "resources": [
            # Resource data structure
        ],
        "stats": {
            # Performance statistics
        }
    }
}
```

## Real RDC Files

For testing with actual RDC files:

1. Place RDC files in a dedicated subdirectory (e.g., `fixtures/rdc_files/`)
2. Ensure files are not too large (preferably under 100MB)
3. Include a metadata file with capture details
4. Consider file size limits for CI/CD pipelines

## Best Practices

1. **Version Control**: Track fixture versions to ensure test consistency
2. **Documentation**: Document the purpose of each fixture
3. **Performance**: Keep fixture loading time minimal
4. **Size**: Keep fixture files reasonable for CI/CD
5. **Relevance**: Update fixtures regularly to match real-world scenarios

## Contributing

When adding new fixtures:

1. Create the fixture file
2. Add tests that use the fixture
3. Update this README with documentation
4. Ensure all tests pass with the new fixture
5. Consider the impact on test execution time

## Mobile Game Testing

For mobile game testing with the mobile-aggressive preset:

- Use realistic mobile GPU constraints
- Include high draw call counts that exceed mobile thresholds
- Include expensive shaders that exceed mobile limits
- Include large textures that exceed mobile memory limits
- Include performance bottlenecks common in mobile games