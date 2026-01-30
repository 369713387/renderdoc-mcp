import json
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

DEFAULT_CONFIG_PATH = Path(__file__).parent / "config.json"

@dataclass
class Thresholds:
    max_draw_calls: int = 1000
    expensive_shader_instructions: int = 500
    large_texture_size: int = 4096
    overdraw_threshold: float = 2.5

    def __post_init__(self):
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
    include_raw_data: bool = False
    verbose: bool = False

@dataclass
class Config:
    thresholds: Thresholds
    output: OutputConfig

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "Config":
        config_path = path or DEFAULT_CONFIG_PATH
        if not config_path.exists():
            return cls(
                thresholds=Thresholds(),
                output=OutputConfig()
            )

        try:
            with open(config_path) as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in config file {config_path}: {e}")

        return cls(
            thresholds=Thresholds(**data.get("thresholds", {})),
            output=OutputConfig(**data.get("output", {}))
        )
