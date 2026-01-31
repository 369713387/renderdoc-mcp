import json
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

DEFAULT_CONFIG_PATH = Path(__file__).parent / "config.json"


@dataclass
class GeometryThresholds:
    """Geometry-related performance thresholds."""
    max_triangles: int = 100000
    max_draw_calls: int = 1000
    max_triangles_per_model: int = 50000

    def __post_init__(self):
        if self.max_draw_calls <= 0:
            raise ValueError(f"max_draw_calls must be positive, got {self.max_draw_calls}")
        if self.max_triangles <= 0:
            raise ValueError(f"max_triangles must be positive, got {self.max_triangles}")
        if self.max_triangles_per_model <= 0:
            raise ValueError(f"max_triangles_per_model must be positive, got {self.max_triangles_per_model}")


@dataclass
class ShaderThresholds:
    """Shader-related performance thresholds."""
    max_vs_instructions: int = 500
    max_fs_instructions: int = 500
    max_cs_instructions: int = 1000

    def __post_init__(self):
        if self.max_vs_instructions < 0:
            raise ValueError(f"max_vs_instructions must be non-negative, got {self.max_vs_instructions}")
        if self.max_fs_instructions < 0:
            raise ValueError(f"max_fs_instructions must be non-negative, got {self.max_fs_instructions}")
        if self.max_cs_instructions < 0:
            raise ValueError(f"max_cs_instructions must be non-negative, got {self.max_cs_instructions}")


@dataclass
class PassThresholds:
    """Render pass-related performance thresholds."""
    max_duration_ms: float = 1.0
    max_overdraw_ratio: float = 2.5
    max_switches_per_frame: int = 20

    def __post_init__(self):
        if self.max_duration_ms <= 0:
            raise ValueError(f"max_duration_ms must be positive, got {self.max_duration_ms}")
        if self.max_overdraw_ratio < 0:
            raise ValueError(f"max_overdraw_ratio must be non-negative, got {self.max_overdraw_ratio}")
        if self.max_switches_per_frame < 0:
            raise ValueError(f"max_switches_per_frame must be non-negative, got {self.max_switches_per_frame}")


@dataclass
class MemoryThresholds:
    """Memory-related performance thresholds."""
    max_texture_size: int = 4096
    require_compressed_textures: bool = False

    def __post_init__(self):
        if self.max_texture_size <= 0:
            raise ValueError(f"max_texture_size must be positive, got {self.max_texture_size}")


@dataclass
class Thresholds:
    """
    Main thresholds container with backward compatibility.

    Maintains old interface while adding new structured thresholds.
    """
    # New structured thresholds
    geometry: GeometryThresholds
    shader: ShaderThresholds
    pass_: PassThresholds  # 'pass' is reserved keyword
    memory: MemoryThresholds

    # Legacy fields for backward compatibility (computed from geometry)
    max_draw_calls: int = 1000
    expensive_shader_instructions: int = 500
    large_texture_size: int = 4096
    overdraw_threshold: float = 2.5

    def __init__(self, data=None, **kwargs):
        """
        Initialize thresholds from optional data dict or kwargs.

        Supports both old (direct kwargs) and new (nested dict) interfaces:
        - Old: Thresholds(max_draw_calls=2000, expensive_shader_instructions=750)
        - New: Thresholds({"geometry": {"max_draw_calls": 2000}, "shader": {...}})

        Args:
            data: Optional dict with threshold categories, or None if using kwargs
            **kwargs: Direct threshold values (legacy interface)
        """
        # Support both dict and kwargs interfaces
        if data is None:
            data = {}

        # If kwargs are provided directly (legacy interface), treat them as old-style thresholds
        if kwargs and not data:
            # Legacy interface: Thresholds(max_draw_calls=2000, ...)
            # Build structured thresholds from legacy kwargs
            geometry_kwargs = {}
            shader_kwargs = {}
            pass_kwargs = {}
            memory_kwargs = {}

            if "max_draw_calls" in kwargs:
                geometry_kwargs["max_draw_calls"] = kwargs["max_draw_calls"]
            if "max_triangles" in kwargs:
                geometry_kwargs["max_triangles"] = kwargs["max_triangles"]
            if "max_triangles_per_model" in kwargs:
                geometry_kwargs["max_triangles_per_model"] = kwargs["max_triangles_per_model"]

            if "expensive_shader_instructions" in kwargs:
                shader_kwargs["max_fs_instructions"] = kwargs["expensive_shader_instructions"]
            if "max_vs_instructions" in kwargs:
                shader_kwargs["max_vs_instructions"] = kwargs["max_vs_instructions"]
            if "max_fs_instructions" in kwargs:
                shader_kwargs["max_fs_instructions"] = kwargs["max_fs_instructions"]
            if "max_cs_instructions" in kwargs:
                shader_kwargs["max_cs_instructions"] = kwargs["max_cs_instructions"]

            if "overdraw_threshold" in kwargs:
                pass_kwargs["max_overdraw_ratio"] = kwargs["overdraw_threshold"]
            if "max_duration_ms" in kwargs:
                pass_kwargs["max_duration_ms"] = kwargs["max_duration_ms"]
            if "max_switches_per_frame" in kwargs:
                pass_kwargs["max_switches_per_frame"] = kwargs["max_switches_per_frame"]

            if "large_texture_size" in kwargs:
                memory_kwargs["max_texture_size"] = kwargs["large_texture_size"]
            if "max_texture_size" in kwargs:
                memory_kwargs["max_texture_size"] = kwargs["max_texture_size"]
            if "require_compressed_textures" in kwargs:
                memory_kwargs["require_compressed_textures"] = kwargs["require_compressed_textures"]

            # Build data dict from legacy kwargs
            data = {
                "geometry": geometry_kwargs,
                "shader": shader_kwargs,
                "pass": pass_kwargs,
                "memory": memory_kwargs
            }

        # Track if using legacy interface for better error messages
        using_legacy_interface = bool(kwargs and not data.get("geometry"))

        try:
            # Initialize new structured thresholds
            self.geometry = GeometryThresholds(**data.get("geometry", {}))
            self.shader = ShaderThresholds(**data.get("shader", {}))
            # Handle both 'pass' and 'pass_' keys
            pass_data = data.get("pass", data.get("pass_", {}))
            self.pass_ = PassThresholds(**pass_data)
            self.memory = MemoryThresholds(**data.get("memory", {}))

            # Initialize legacy fields for backward compatibility
            self.max_draw_calls = self.geometry.max_draw_calls
            self.expensive_shader_instructions = self.shader.max_fs_instructions
            self.large_texture_size = self.memory.max_texture_size
            self.overdraw_threshold = self.pass_.max_overdraw_ratio

        except ValueError as e:
            # Convert new field names to legacy field names in error messages
            # if using legacy interface
            if using_legacy_interface:
                error_msg = str(e)
                error_msg = error_msg.replace("max_fs_instructions", "expensive_shader_instructions")
                error_msg = error_msg.replace("max_texture_size", "large_texture_size")
                error_msg = error_msg.replace("max_overdraw_ratio", "overdraw_threshold")
                raise ValueError(error_msg) from e
            raise

        # Legacy validation
        self._validate_legacy()

    def _validate_legacy(self):
        """Run legacy validations for backward compatibility."""
        if self.max_draw_calls <= 0:
            raise ValueError(f"max_draw_calls must be positive, got {self.max_draw_calls}")
        if self.expensive_shader_instructions < 0:
            raise ValueError(f"expensive_shader_instructions must be non-negative, got {self.expensive_shader_instructions}")
        if self.large_texture_size <= 0:
            raise ValueError(f"large_texture_size must be positive, got {self.large_texture_size}")
        if self.overdraw_threshold < 0:
            raise ValueError(f"overdraw_threshold must be non-negative, got {self.overdraw_threshold}")


@dataclass
class OutputConfig:
    """Output configuration options."""
    include_raw_data: bool = False
    verbose: bool = False


class Config:
    """
    Main configuration class with preset support.

    Supports loading from:
    - Preset configurations (mobile-aggressive, mobile-balanced, pc-balanced)
    - Custom config files
    - Default values
    """

    def __init__(self, preset=None, overrides=None):
        """
        Initialize configuration.

        Args:
            preset: Optional preset name to load
            overrides: Optional dict of threshold overrides
        """
        if preset:
            self.thresholds = self._load_preset(preset, overrides)
        else:
            self.thresholds = Thresholds(overrides)
        self.output = OutputConfig()

    @staticmethod
    def _load_preset(name: str, overrides=None) -> Thresholds:
        """
        Load preset configuration.

        Args:
            name: Preset name (e.g., 'mobile-aggressive')
            overrides: Optional dict of threshold overrides

        Returns:
            Thresholds instance

        Raises:
            FileNotFoundError: If preset file doesn't exist
        """
        preset_dir = Path(__file__).parent / "presets"
        preset_file = preset_dir / f"{name}.json"

        if not preset_file.exists():
            raise FileNotFoundError(f"Preset not found: {name}")

        with open(preset_file, encoding='utf-8') as f:
            data = json.load(f)

        # Extract thresholds section
        thresholds_data = data.get("thresholds", {})

        # Deep merge overrides
        if overrides:
            for category, values in overrides.items():
                if category in thresholds_data:
                    thresholds_data[category].update(values)
                else:
                    thresholds_data[category] = values

        return Thresholds(thresholds_data)

    @staticmethod
    def load_preset(name: str, overrides=None) -> 'Config':
        """
        Load preset and return Config instance.

        Args:
            name: Preset name (e.g., 'mobile-aggressive')
            overrides: Optional dict of threshold overrides

        Returns:
            Config instance with preset loaded
        """
        return Config(preset=name, overrides=overrides)

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "Config":
        """
        Load config from file or use defaults.

        Supports both old and new config formats:
        - Old format: Direct threshold values
        - New format: preset + optional overrides

        Args:
            path: Optional path to config file

        Returns:
            Config instance

        Raises:
            ValueError: If JSON is invalid
        """
        config_path = path or DEFAULT_CONFIG_PATH
        if not config_path.exists():
            return cls()

        try:
            with open(config_path, encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in config file {config_path}: {e}")

        # Check for new preset-based format
        if "preset" in data:
            preset = data.get("preset")
            overrides = data.get("thresholds")
            return cls.load_preset(preset, overrides)

        # Old format - direct threshold values
        thresholds_data = data.get("thresholds", {})
        output_data = data.get("output", {})

        # Check if thresholds_data uses new structured format or old flat format
        if thresholds_data and any(key in thresholds_data for key in ["geometry", "shader", "pass", "pass_", "memory"]):
            # New structured format
            config = cls()
            config.thresholds = Thresholds(thresholds_data)
        else:
            # Old flat format - convert to kwargs for backward compatibility
            config = cls()
            config.thresholds = Thresholds(**thresholds_data)

        config.output = OutputConfig(**output_data)

        return config
