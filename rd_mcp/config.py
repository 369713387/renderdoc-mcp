# rd_mcp/config.py
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

        with open(config_path) as f:
            data = json.load(f)

        return cls(
            thresholds=Thresholds(**data.get("thresholds", {})),
            output=OutputConfig(**data.get("output", {}))
        )
