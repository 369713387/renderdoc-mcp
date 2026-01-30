import json
import tempfile
from pathlib import Path
import pytest

from rd_mcp.config import Config, Thresholds, OutputConfig, DEFAULT_CONFIG_PATH


class TestThresholdsValidation:
    """Test validation of threshold values."""

    def test_default_thresholds_are_valid(self):
        """Test that default threshold values are valid."""
        thresholds = Thresholds()
        assert thresholds.max_draw_calls == 1000
        assert thresholds.expensive_shader_instructions == 500
        assert thresholds.large_texture_size == 4096
        assert thresholds.overdraw_threshold == 2.5

    def test_max_draw_calls_must_be_positive(self):
        """Test that max_draw_calls must be positive."""
        with pytest.raises(ValueError, match="max_draw_calls must be positive"):
            Thresholds(max_draw_calls=0)

        with pytest.raises(ValueError, match="max_draw_calls must be positive"):
            Thresholds(max_draw_calls=-100)

    def test_expensive_shader_instructions_must_be_non_negative(self):
        """Test that expensive_shader_instructions must be non-negative."""
        with pytest.raises(ValueError, match="expensive_shader_instructions must be non-negative"):
            Thresholds(expensive_shader_instructions=-1)

        # Should not raise for zero
        thresholds = Thresholds(expensive_shader_instructions=0)
        assert thresholds.expensive_shader_instructions == 0

    def test_large_texture_size_must_be_positive(self):
        """Test that large_texture_size must be positive."""
        with pytest.raises(ValueError, match="large_texture_size must be positive"):
            Thresholds(large_texture_size=0)

        with pytest.raises(ValueError, match="large_texture_size must be positive"):
            Thresholds(large_texture_size=-100)

    def test_overdraw_threshold_must_be_non_negative(self):
        """Test that overdraw_threshold must be non-negative."""
        with pytest.raises(ValueError, match="overdraw_threshold must be non-negative"):
            Thresholds(overdraw_threshold=-1.0)

        # Should not raise for zero
        thresholds = Thresholds(overdraw_threshold=0.0)
        assert thresholds.overdraw_threshold == 0.0

    def test_all_validations_run_together(self):
        """Test that all validations are checked."""
        with pytest.raises(ValueError, match="max_draw_calls must be positive"):
            Thresholds(
                max_draw_calls=-1,
                expensive_shader_instructions=-1,
                large_texture_size=-1,
                overdraw_threshold=-1.0
            )


class TestConfigLoading:
    """Test configuration loading from files."""

    def test_load_default_config_when_file_missing(self):
        """Test that default config is returned when file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            nonexistent_path = Path(tmpdir) / "nonexistent.json"
            config = Config.load(nonexistent_path)

            assert isinstance(config, Config)
            assert isinstance(config.thresholds, Thresholds)
            assert isinstance(config.output, OutputConfig)
            assert config.thresholds.max_draw_calls == 1000
            assert config.output.include_raw_data is False

    def test_load_valid_config_file(self):
        """Test loading a valid configuration file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config_data = {
                "thresholds": {
                    "max_draw_calls": 2000,
                    "expensive_shader_instructions": 750,
                    "large_texture_size": 8192,
                    "overdraw_threshold": 3.0
                },
                "output": {
                    "include_raw_data": True,
                    "verbose": True
                }
            }
            json.dump(config_data, f)
            f.flush()
            config_path = Path(f.name)

        try:
            config = Config.load(config_path)

            assert config.thresholds.max_draw_calls == 2000
            assert config.thresholds.expensive_shader_instructions == 750
            assert config.thresholds.large_texture_size == 8192
            assert config.thresholds.overdraw_threshold == 3.0
            assert config.output.include_raw_data is True
            assert config.output.verbose is True
        finally:
            config_path.unlink()

    def test_load_partial_config_uses_defaults(self):
        """Test that partial config uses defaults for missing fields."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config_data = {
                "thresholds": {
                    "max_draw_calls": 1500
                    # Missing other threshold fields
                },
                "output": {
                    "verbose": True
                    # Missing include_raw_data
                }
            }
            json.dump(config_data, f)
            f.flush()
            config_path = Path(f.name)

        try:
            config = Config.load(config_path)

            # Provided values
            assert config.thresholds.max_draw_calls == 1500
            assert config.output.verbose is True

            # Default values
            assert config.thresholds.expensive_shader_instructions == 500
            assert config.thresholds.large_texture_size == 4096
            assert config.thresholds.overdraw_threshold == 2.5
            assert config.output.include_raw_data is False
        finally:
            config_path.unlink()

    def test_load_empty_config_uses_all_defaults(self):
        """Test that empty config file uses all defaults."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config_data = {}
            json.dump(config_data, f)
            f.flush()
            config_path = Path(f.name)

        try:
            config = Config.load(config_path)

            assert config.thresholds.max_draw_calls == 1000
            assert config.thresholds.expensive_shader_instructions == 500
            assert config.thresholds.large_texture_size == 4096
            assert config.thresholds.overdraw_threshold == 2.5
            assert config.output.include_raw_data is False
            assert config.output.verbose is False
        finally:
            config_path.unlink()

    def test_load_malformed_json_raises_helpful_error(self):
        """Test that malformed JSON raises a helpful error message."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('{ invalid json }')
            f.flush()
            config_path = Path(f.name)

        try:
            with pytest.raises(ValueError, match="Invalid JSON in config file"):
                Config.load(config_path)
        finally:
            config_path.unlink()

    def test_load_invalid_threshold_values_raises_error(self):
        """Test that invalid threshold values in config file raise errors."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config_data = {
                "thresholds": {
                    "max_draw_calls": -100,  # Invalid
                    "expensive_shader_instructions": 500,
                    "large_texture_size": 4096,
                    "overdraw_threshold": 2.5
                },
                "output": {
                    "include_raw_data": False,
                    "verbose": False
                }
            }
            json.dump(config_data, f)
            f.flush()
            config_path = Path(f.name)

        try:
            with pytest.raises(ValueError, match="max_draw_calls must be positive"):
                Config.load(config_path)
        finally:
            config_path.unlink()

    def test_load_multiple_invalid_thresholds(self):
        """Test that multiple invalid threshold values are caught."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config_data = {
                "thresholds": {
                    "max_draw_calls": 0,  # Invalid
                    "expensive_shader_instructions": -10,  # Invalid
                    "large_texture_size": 4096,
                    "overdraw_threshold": -1.0  # Invalid
                },
                "output": {
                    "include_raw_data": False,
                    "verbose": False
                }
            }
            json.dump(config_data, f)
            f.flush()
            config_path = Path(f.name)

        try:
            # Should raise on first validation failure
            with pytest.raises(ValueError):
                Config.load(config_path)
        finally:
            config_path.unlink()

    def test_missing_thresholds_section(self):
        """Test config file without thresholds section."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config_data = {
                "output": {
                    "include_raw_data": True
                }
            }
            json.dump(config_data, f)
            f.flush()
            config_path = Path(f.name)

        try:
            config = Config.load(config_path)
            assert config.thresholds.max_draw_calls == 1000  # Default
            assert config.output.include_raw_data is True
        finally:
            config_path.unlink()

    def test_missing_output_section(self):
        """Test config file without output section."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config_data = {
                "thresholds": {
                    "max_draw_calls": 2000
                }
            }
            json.dump(config_data, f)
            f.flush()
            config_path = Path(f.name)

        try:
            config = Config.load(config_path)
            assert config.thresholds.max_draw_calls == 2000
            assert config.output.include_raw_data is False  # Default
        finally:
            config_path.unlink()


class TestOutputConfig:
    """Test OutputConfig dataclass."""

    def test_default_output_config(self):
        """Test default output configuration values."""
        output = OutputConfig()
        assert output.include_raw_data is False
        assert output.verbose is False

    def test_custom_output_config(self):
        """Test custom output configuration values."""
        output = OutputConfig(include_raw_data=True, verbose=True)
        assert output.include_raw_data is True
        assert output.verbose is True
