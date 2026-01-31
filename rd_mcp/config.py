import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

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
class MaliThresholds:
    """Mali GPU-specific shader analysis thresholds.
    
    These thresholds are used by the MaliComplexityDetector when
    analyzing shaders with the Mali Offline Compiler (malioc).
    """
    # Enable/disable Mali analysis (defaults to False to avoid malioc-not-found messages)
    enabled: bool = False
    
    # Target Mali GPU for analysis
    target_gpu: str = "Mali-G78"
    
    # Cycle count thresholds
    max_cycles: int = 50  # Maximum acceptable total cycles
    max_cycles_critical: int = 100  # Cycles threshold for critical severity
    
    # Register usage thresholds
    max_registers: int = 32  # Maximum work registers before warning
    
    # Texture and sampling thresholds
    max_texture_samples: int = 8  # Maximum texture samples per shader
    
    # Branching thresholds
    max_branches: int = 10  # Maximum branch instructions
    
    # Optional malioc path (None = auto-detect)
    malioc_path: Optional[str] = None

    def __post_init__(self):
        if self.max_cycles < 0:
            raise ValueError(f"max_cycles must be non-negative, got {self.max_cycles}")
        if self.max_registers < 0:
            raise ValueError(f"max_registers must be non-negative, got {self.max_registers}")
        if self.max_texture_samples < 0:
            raise ValueError(f"max_texture_samples must be non-negative, got {self.max_texture_samples}")
        if self.max_branches < 0:
            raise ValueError(f"max_branches must be non-negative, got {self.max_branches}")
    
    def to_detector_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format expected by MaliComplexityDetector."""
        return {
            "mali_enabled": self.enabled,
            "mali_target_gpu": self.target_gpu,
            "mali_max_cycles": self.max_cycles,
            "mali_max_registers": self.max_registers,
            "mali_max_texture_samples": self.max_texture_samples,
            "mali_max_branches": self.max_branches,
            "mali_malioc_path": self.malioc_path,
        }


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

    Provides structured thresholds for different performance categories while
    maintaining legacy property-based access for backward compatibility.

    The __init__ method accepts both structured data and legacy kwargs for backward compatibility.

    Examples:
        >>> # Default thresholds
        >>> thresholds = Thresholds()
        >>> # Legacy kwargs (backward compatible)
        >>> thresholds = Thresholds(max_draw_calls=2000)
        >>> # Structured data
        >>> thresholds = Thresholds(data={"geometry": {"max_draw_calls": 2000}})
    """

    geometry: GeometryThresholds = field(default_factory=GeometryThresholds)
    shader: ShaderThresholds = field(default_factory=ShaderThresholds)
    pass_: PassThresholds = field(default_factory=PassThresholds)
    memory: MemoryThresholds = field(default_factory=MemoryThresholds)
    mali: MaliThresholds = field(default_factory=MaliThresholds)

    def __init__(self, data=None, **kwargs):
        """
        Initialize thresholds with backward compatibility support.

        This method delegates to from_dict() which handles both legacy kwargs
        and structured data formats.

        Args:
            data: Optional dict with threshold categories
            **kwargs: Legacy threshold values (e.g., max_draw_calls, expensive_shader_instructions)
        """
        # Use the dataclass-generated fields only if neither data nor kwargs provided
        if data is None and not kwargs:
            # Let dataclass handle default initialization
            self.geometry = GeometryThresholds()
            self.shader = ShaderThresholds()
            self.pass_ = PassThresholds()
            self.memory = MemoryThresholds()
            self.mali = MaliThresholds()
        else:
            # Delegate to from_dict for all other cases
            result = self.from_dict(data, **kwargs)
            # Copy the result's fields to self
            self.geometry = result.geometry
            self.shader = result.shader
            self.pass_ = result.pass_
            self.memory = result.memory
            self.mali = result.mali

    @classmethod
    def from_legacy(cls, **kwargs) -> 'Thresholds':
        """
        Create Thresholds from legacy keyword arguments.

        Maps old-style flat parameter names to new structured format.

        Args:
            **kwargs: Legacy threshold values (e.g., max_draw_calls, expensive_shader_instructions)

        Returns:
            Thresholds instance with structured thresholds

        Examples:
            >>> thresholds = Thresholds.from_legacy(max_draw_calls=2000)
            >>> thresholds.geometry.max_draw_calls
            2000
        """
        geometry_kwargs = {}
        shader_kwargs = {}
        pass_kwargs = {}
        memory_kwargs = {}

        # Map legacy geometry fields
        if "max_draw_calls" in kwargs:
            geometry_kwargs["max_draw_calls"] = kwargs["max_draw_calls"]
        if "max_triangles" in kwargs:
            geometry_kwargs["max_triangles"] = kwargs["max_triangles"]
        if "max_triangles_per_model" in kwargs:
            geometry_kwargs["max_triangles_per_model"] = kwargs["max_triangles_per_model"]

        # Map legacy shader fields
        if "expensive_shader_instructions" in kwargs:
            shader_kwargs["max_fs_instructions"] = kwargs["expensive_shader_instructions"]
        if "max_vs_instructions" in kwargs:
            shader_kwargs["max_vs_instructions"] = kwargs["max_vs_instructions"]
        if "max_fs_instructions" in kwargs:
            shader_kwargs["max_fs_instructions"] = kwargs["max_fs_instructions"]
        if "max_cs_instructions" in kwargs:
            shader_kwargs["max_cs_instructions"] = kwargs["max_cs_instructions"]

        # Map legacy pass fields
        if "overdraw_threshold" in kwargs:
            pass_kwargs["max_overdraw_ratio"] = kwargs["overdraw_threshold"]
        if "max_duration_ms" in kwargs:
            pass_kwargs["max_duration_ms"] = kwargs["max_duration_ms"]
        if "max_switches_per_frame" in kwargs:
            pass_kwargs["max_switches_per_frame"] = kwargs["max_switches_per_frame"]

        # Map legacy memory fields
        if "large_texture_size" in kwargs:
            memory_kwargs["max_texture_size"] = kwargs["large_texture_size"]
        if "max_texture_size" in kwargs:
            memory_kwargs["max_texture_size"] = kwargs["max_texture_size"]
        if "require_compressed_textures" in kwargs:
            memory_kwargs["require_compressed_textures"] = kwargs["require_compressed_textures"]

        try:
            # Use object.__new__ to avoid calling __init__ and prevent recursion
            instance = object.__new__(cls)
            instance.geometry = GeometryThresholds(**geometry_kwargs)
            instance.shader = ShaderThresholds(**shader_kwargs)
            instance.pass_ = PassThresholds(**pass_kwargs)
            instance.memory = MemoryThresholds(**memory_kwargs)
            instance.mali = MaliThresholds()  # Use defaults for legacy format
            return instance
        except ValueError as e:
            # Convert new field names to legacy field names in error messages
            error_msg = str(e)
            error_msg = error_msg.replace("max_fs_instructions", "expensive_shader_instructions")
            error_msg = error_msg.replace("max_texture_size", "large_texture_size")
            error_msg = error_msg.replace("max_overdraw_ratio", "overdraw_threshold")
            raise ValueError(error_msg) from e

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]] = None, **kwargs) -> 'Thresholds':
        """
        Create Thresholds from dictionary or legacy kwargs.

        This factory method supports both the new structured format and legacy kwargs,
        providing backward compatibility.

        Args:
            data: Optional dict with threshold categories (new format) or legacy flat values
            **kwargs: Direct threshold values (legacy format)

        Returns:
            Thresholds instance

        Raises:
            ValueError: If both data dict and kwargs are provided with conflicting data

        Examples:
            >>> # New format
            >>> thresholds = Thresholds.from_dict({
            ...     "geometry": {"max_draw_calls": 2000},
            ...     "shader": {"max_fs_instructions": 750}
            ... })
            >>> # Legacy format (as data dict)
            >>> thresholds = Thresholds.from_dict({"max_draw_calls": 2000})
            >>> # Legacy format (as kwargs)
            >>> thresholds = Thresholds.from_dict(max_draw_calls=2000)
        """
        if data is None:
            data = {}

        # Detect if data dict is using legacy flat format (not structured format)
        is_legacy_flat_format = (
            data and
            not any(key in data for key in ["geometry", "shader", "pass", "pass_", "memory"])
        )

        # If data is legacy flat format, convert it to kwargs
        if is_legacy_flat_format:
            return cls.from_legacy(**data, **kwargs)

        # Validate mutually exclusive parameters
        if data and kwargs:
            # Check if there's actual overlap
            data_keys = set()
            for category in ["geometry", "shader", "pass", "pass_", "memory"]:
                if category in data:
                    data_keys.update(data[category].keys())

            # Map legacy names to check overlap
            legacy_mappings = {
                "max_draw_calls": "geometry",
                "max_triangles": "geometry",
                "max_triangles_per_model": "geometry",
                "expensive_shader_instructions": "shader",
                "max_vs_instructions": "shader",
                "max_fs_instructions": "shader",
                "max_cs_instructions": "shader",
                "overdraw_threshold": "pass",
                "max_duration_ms": "pass",
                "max_switches_per_frame": "pass",
                "large_texture_size": "memory",
                "max_texture_size": "memory",
                "require_compressed_textures": "memory"
            }

            overlapping_keys = set(kwargs.keys()) & data_keys
            if overlapping_keys:
                raise ValueError(
                    f"Cannot specify both data dict and kwargs for overlapping keys: {overlapping_keys}"
                )

        # If kwargs are provided directly, use legacy conversion
        if kwargs and not data:
            return cls.from_legacy(**kwargs)

        # Handle both 'pass' and 'pass_' keys in data dict
        # Use object.__new__ to avoid calling __init__ and prevent recursion
        instance = object.__new__(cls)
        instance.geometry = GeometryThresholds(**data.get("geometry", {}))
        instance.shader = ShaderThresholds(**data.get("shader", {}))
        instance.pass_ = PassThresholds(**data.get("pass", data.get("pass_", {})))
        instance.memory = MemoryThresholds(**data.get("memory", {}))
        instance.mali = MaliThresholds(**data.get("mali", {}))
        return instance

    # Legacy compatibility properties (not stored fields)
    @property
    def max_draw_calls(self) -> int:
        """Legacy property for backward compatibility."""
        return self.geometry.max_draw_calls

    @property
    def expensive_shader_instructions(self) -> int:
        """Legacy property for backward compatibility."""
        return self.shader.max_fs_instructions

    @property
    def large_texture_size(self) -> int:
        """Legacy property for backward compatibility."""
        return self.memory.max_texture_size

    @property
    def overdraw_threshold(self) -> float:
        """Legacy property for backward compatibility."""
        return self.pass_.max_overdraw_ratio

    def to_legacy_dict(self) -> Dict[str, Any]:
        """
        Convert thresholds to legacy flat dictionary format.

        This is useful for passing to detectors that expect the old flat format.

        Returns:
            Dict with legacy field names and values
        """
        result = {
            "max_draw_calls": self.max_draw_calls,
            "max_triangles": self.geometry.max_triangles,
            "max_triangles_per_model": self.geometry.max_triangles_per_model,
            "expensive_shader_instructions": self.expensive_shader_instructions,
            "max_vs_instructions": self.shader.max_vs_instructions,
            "max_fs_instructions": self.shader.max_fs_instructions,
            "max_cs_instructions": self.shader.max_cs_instructions,
            "overdraw_threshold": self.overdraw_threshold,
            "max_duration_ms": self.pass_.max_duration_ms,
            "max_switches_per_frame": self.pass_.max_switches_per_frame,
            "large_texture_size": self.large_texture_size,
            "max_texture_size": self.memory.max_texture_size,
            "require_compressed_textures": self.memory.require_compressed_textures
        }
        
        # Add Mali thresholds
        result.update(self.mali.to_detector_dict())
        
        return result


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
            self.thresholds = Thresholds.from_dict(overrides)
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

        return Thresholds.from_dict(thresholds_data)

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
        config = cls()
        config.thresholds = Thresholds.from_dict(thresholds_data)

        config.output = OutputConfig(**output_data)

        return config
