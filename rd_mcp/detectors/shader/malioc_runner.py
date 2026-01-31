# rd_mcp/detectors/shader/malioc_runner.py
"""Mali Offline Compiler (malioc) command runner.

This module provides functionality to execute malioc commands and
parse the output to extract shader performance metrics.
"""

import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# Common malioc installation paths
MALIOC_PATHS = [
    # Windows
    r"C:\Program Files\Arm\Mali Developer Tools\Mali Offline Compiler\malioc.exe",
    r"C:\Program Files\Arm GPU Tools\Mali Offline Compiler\malioc.exe",
    r"C:\Program Files (x86)\Arm\Mali Developer Tools\Mali Offline Compiler\malioc.exe",
    # Linux
    "/opt/arm/mali-offline-compiler/bin/malioc",
    "/usr/local/bin/malioc",
    "/usr/bin/malioc",
    # macOS
    "/Applications/Arm/Mali Developer Tools/Mali Offline Compiler/malioc",
]

# Supported Mali GPU targets
MALI_GPU_TARGETS = [
    "Mali-G78",
    "Mali-G77",
    "Mali-G76",
    "Mali-G72",
    "Mali-G71",
    "Mali-G57",
    "Mali-G52",
    "Mali-G51",
    "Mali-G31",
    "Mali-T880",
    "Mali-T860",
    "Mali-T760",
]

# Shader stage to file extension mapping
STAGE_TO_EXTENSION = {
    "vertex": ".vert",
    "fragment": ".frag",
    "compute": ".comp",
    "geometry": ".geom",
    "tesscontrol": ".tesc",
    "tessevaluation": ".tese",
}


@dataclass
class MaliocOutput:
    """Parsed output from malioc command.
    
    Contains all metrics extracted from malioc analysis.
    """
    # Success status
    success: bool = False
    error_message: str = ""
    
    # Target info
    target_gpu: str = ""
    driver_version: str = ""
    
    # Performance metrics
    work_registers: int = 0
    uniform_registers: int = 0
    stack_spilling: bool = False
    
    # Cycle counts (per pipeline stage)
    total_cycles: float = 0.0
    shortest_path_cycles: float = 0.0
    longest_path_cycles: float = 0.0
    
    # Per-unit cycles
    arithmetic_cycles: float = 0.0
    load_store_cycles: float = 0.0
    varying_cycles: float = 0.0
    texture_cycles: float = 0.0
    
    # Instruction counts
    total_instructions: int = 0
    arithmetic_instructions: int = 0
    load_store_instructions: int = 0
    texture_instructions: int = 0
    branch_instructions: int = 0
    
    # Additional info
    has_uniform_computation: bool = False
    has_side_effects: bool = False
    
    # Raw output
    raw_text: str = ""
    raw_json: Dict[str, Any] = field(default_factory=dict)


class MaliocRunner:
    """Runner for Mali Offline Compiler (malioc).
    
    Provides methods to:
    - Find and validate malioc installation
    - Execute malioc on shader source code
    - Parse malioc output to extract metrics
    
    Example:
        >>> runner = MaliocRunner()
        >>> if runner.is_available():
        ...     metrics = runner.analyze_shader(
        ...         source="void main() { gl_FragColor = vec4(1.0); }",
        ...         stage="Fragment",
        ...         shader_name="simple_frag"
        ...     )
        ...     print(f"Cycles: {metrics.total_cycles}")
    """
    
    def __init__(self, malioc_path: Optional[str] = None):
        """Initialize the malioc runner.
        
        Args:
            malioc_path: Optional explicit path to malioc executable.
                        If None, searches standard locations.
        """
        self._malioc_path = malioc_path
        self._cached_path: Optional[str] = None
        self._version: Optional[str] = None
        self._available: Optional[bool] = None
    
    def _find_malioc(self) -> Optional[str]:
        """Find the malioc executable.
        
        Returns:
            Path to malioc executable, or None if not found
        """
        # Check explicit path first
        if self._malioc_path:
            if Path(self._malioc_path).exists():
                return self._malioc_path
            logger.warning(f"Specified malioc path not found: {self._malioc_path}")
        
        # Check environment variable
        env_path = os.environ.get("MALIOC_PATH")
        if env_path and Path(env_path).exists():
            return env_path
        
        # Try to find in PATH
        malioc_in_path = shutil.which("malioc")
        if malioc_in_path:
            return malioc_in_path
        
        # Check common installation paths
        for path in MALIOC_PATHS:
            if Path(path).exists():
                return path
        
        return None
    
    def get_path(self) -> Optional[str]:
        """Get the path to malioc executable.
        
        Returns:
            Path to malioc, or None if not found
        """
        if self._cached_path is None:
            self._cached_path = self._find_malioc()
        return self._cached_path
    
    def is_available(self) -> bool:
        """Check if malioc is available on the system.
        
        Returns:
            True if malioc is found and executable
        """
        if self._available is None:
            path = self.get_path()
            if path is None:
                self._available = False
            else:
                # Try to run malioc --version to verify it works
                try:
                    result = subprocess.run(
                        [path, "--version"],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    self._available = result.returncode == 0
                except Exception as e:
                    logger.warning(f"malioc check failed: {e}")
                    self._available = False
        return self._available
    
    def get_version(self) -> str:
        """Get the malioc version string.
        
        Returns:
            Version string, or empty string if not available
        """
        if self._version is None:
            if not self.is_available():
                self._version = ""
            else:
                try:
                    result = subprocess.run(
                        [self.get_path(), "--version"],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    if result.returncode == 0:
                        # Parse version from output (format: "Mali Offline Compiler v7.x.x")
                        match = re.search(r'v?(\d+\.\d+\.\d+)', result.stdout)
                        self._version = match.group(1) if match else result.stdout.strip()
                    else:
                        self._version = ""
                except Exception:
                    self._version = ""
        return self._version
    
    def get_supported_gpus(self) -> List[str]:
        """Get list of supported GPU targets.
        
        Returns:
            List of supported Mali GPU names
        """
        return MALI_GPU_TARGETS.copy()
    
    def analyze_shader(
        self,
        source: str,
        stage: str,
        shader_name: str = "shader",
        target_gpu: str = "Mali-G78",
        extra_args: Optional[List[str]] = None
    ) -> Optional['MaliShaderMetrics']:
        """Analyze a shader using malioc.
        
        Args:
            source: GLSL shader source code
            stage: Shader stage (Vertex, Fragment, Compute, etc.)
            shader_name: Name for the shader (for reporting)
            target_gpu: Target Mali GPU (default: Mali-G78)
            extra_args: Additional command line arguments for malioc
            
        Returns:
            MaliShaderMetrics with analysis results, or None if analysis failed
        """
        if not self.is_available():
            logger.warning("malioc not available, cannot analyze shader")
            return None
        
        # Normalize stage name
        stage_lower = stage.lower()
        if stage_lower not in STAGE_TO_EXTENSION:
            logger.warning(f"Unknown shader stage: {stage}")
            # Default to fragment shader for unknown stages
            stage_lower = "fragment"
        
        # Run malioc and get output
        output = self._run_malioc(source, stage_lower, target_gpu, extra_args)
        
        if not output.success:
            logger.warning(f"malioc analysis failed: {output.error_message}")
            return None
        
        # Convert MaliocOutput to MaliShaderMetrics
        from rd_mcp.detectors.shader.mali_complexity import MaliShaderMetrics
        
        return MaliShaderMetrics(
            shader_name=shader_name,
            stage=stage.capitalize(),
            total_cycles=output.total_cycles,
            shortest_path_cycles=output.shortest_path_cycles,
            longest_path_cycles=output.longest_path_cycles,
            arithmetic_cycles=output.arithmetic_cycles,
            load_store_cycles=output.load_store_cycles,
            texture_cycles=output.texture_cycles,
            varying_cycles=output.varying_cycles,
            work_registers=output.work_registers,
            uniform_registers=output.uniform_registers,
            stack_spilling=output.stack_spilling,
            total_instructions=output.total_instructions,
            arithmetic_instructions=output.arithmetic_instructions,
            load_store_instructions=output.load_store_instructions,
            texture_instructions=output.texture_instructions,
            branch_instructions=output.branch_instructions,
            texture_samples=output.texture_instructions,  # Approximate
            has_source=True,
            source_lines=source.count('\n') + 1,
            raw_output=output.raw_text
        )
    
    def _run_malioc(
        self,
        source: str,
        stage: str,
        target_gpu: str,
        extra_args: Optional[List[str]] = None
    ) -> MaliocOutput:
        """Run malioc on shader source.
        
        Args:
            source: GLSL shader source code
            stage: Shader stage (lowercase)
            target_gpu: Target Mali GPU
            extra_args: Additional command line arguments
            
        Returns:
            MaliocOutput with parsed results
        """
        output = MaliocOutput()
        
        # Create temporary file for shader source
        extension = STAGE_TO_EXTENSION.get(stage, ".frag")
        
        try:
            with tempfile.NamedTemporaryFile(
                mode='w',
                suffix=extension,
                delete=False,
                encoding='utf-8'
            ) as f:
                f.write(source)
                shader_path = f.name
            
            # Build command
            cmd = [
                self.get_path(),
                "--core", target_gpu,
                shader_path
            ]
            
            # Add extra arguments
            if extra_args:
                cmd.extend(extra_args)
            
            # Run malioc
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                encoding='utf-8',
                errors='ignore'
            )
            
            output.raw_text = result.stdout + result.stderr
            
            if result.returncode != 0:
                output.success = False
                output.error_message = f"malioc returned {result.returncode}: {result.stderr}"
                return output
            
            # Parse the output
            output = self._parse_text_output(result.stdout, output)
            output.success = True
            output.target_gpu = target_gpu
            
        except subprocess.TimeoutExpired:
            output.success = False
            output.error_message = "malioc timed out"
        except Exception as e:
            output.success = False
            output.error_message = str(e)
        finally:
            # Cleanup temp file
            try:
                Path(shader_path).unlink()
            except Exception:
                pass
        
        return output
    
    def _parse_text_output(self, text: str, output: MaliocOutput) -> MaliocOutput:
        """Parse malioc text output.
        
        malioc output format varies by version, but typically includes:
        - Work registers: N
        - Uniform registers: N
        - Stack spilling: Yes/No
        - Arithmetic: N cycles
        - Load/Store: N cycles
        - Varying: N cycles
        - Texture: N cycles
        - Total cycles: N
        
        Args:
            text: Raw malioc output text
            output: MaliocOutput to populate
            
        Returns:
            Updated MaliocOutput
        """
        lines = text.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            
            # Work registers
            match = re.search(r'Work registers:\s*(\d+)', line)
            if match:
                output.work_registers = int(match.group(1))
                continue
            
            # Uniform registers
            match = re.search(r'Uniform registers:\s*(\d+)', line)
            if match:
                output.uniform_registers = int(match.group(1))
                continue
            
            # Stack spilling
            if 'Stack spilling' in line:
                output.stack_spilling = 'Yes' in line or 'true' in line.lower()
                continue
            
            # Arithmetic cycles
            match = re.search(r'Arithmetic:\s*([\d.]+)\s*(?:cycles?)?', line, re.IGNORECASE)
            if match:
                output.arithmetic_cycles = float(match.group(1))
                continue
            
            # Load/Store cycles
            match = re.search(r'Load/Store:\s*([\d.]+)\s*(?:cycles?)?', line, re.IGNORECASE)
            if match:
                output.load_store_cycles = float(match.group(1))
                continue
            
            # Varying cycles
            match = re.search(r'Varying:\s*([\d.]+)\s*(?:cycles?)?', line, re.IGNORECASE)
            if match:
                output.varying_cycles = float(match.group(1))
                continue
            
            # Texture cycles
            match = re.search(r'Texture:\s*([\d.]+)\s*(?:cycles?)?', line, re.IGNORECASE)
            if match:
                output.texture_cycles = float(match.group(1))
                continue
            
            # Total cycles (various formats)
            match = re.search(r'Total\s+(?:instruction\s+)?cycles:\s*([\d.]+)', line, re.IGNORECASE)
            if match:
                output.total_cycles = float(match.group(1))
                continue
            
            # Shortest/longest path cycles
            match = re.search(r'Shortest path cycles:\s*([\d.]+)', line, re.IGNORECASE)
            if match:
                output.shortest_path_cycles = float(match.group(1))
                continue
            
            match = re.search(r'Longest path cycles:\s*([\d.]+)', line, re.IGNORECASE)
            if match:
                output.longest_path_cycles = float(match.group(1))
                continue
            
            # Instruction counts
            match = re.search(r'Total instructions:\s*(\d+)', line, re.IGNORECASE)
            if match:
                output.total_instructions = int(match.group(1))
                continue
            
            # Arithmetic instructions
            match = re.search(r'Arithmetic instructions:\s*(\d+)', line, re.IGNORECASE)
            if match:
                output.arithmetic_instructions = int(match.group(1))
                continue
            
            # Load/Store instructions
            match = re.search(r'Load/Store instructions:\s*(\d+)', line, re.IGNORECASE)
            if match:
                output.load_store_instructions = int(match.group(1))
                continue
            
            # Texture instructions
            match = re.search(r'Texture instructions:\s*(\d+)', line, re.IGNORECASE)
            if match:
                output.texture_instructions = int(match.group(1))
                continue
            
            # Branch instructions
            match = re.search(r'Branch instructions:\s*(\d+)', line, re.IGNORECASE)
            if match:
                output.branch_instructions = int(match.group(1))
                continue
        
        # Calculate total cycles if not found directly
        if output.total_cycles == 0:
            output.total_cycles = max(
                output.arithmetic_cycles,
                output.load_store_cycles,
                output.varying_cycles,
                output.texture_cycles
            )
        
        return output
    
    def _parse_json_output(self, json_str: str, output: MaliocOutput) -> MaliocOutput:
        """Parse malioc JSON output (if available in newer versions).
        
        Args:
            json_str: JSON output from malioc
            output: MaliocOutput to populate
            
        Returns:
            Updated MaliocOutput
        """
        try:
            data = json.loads(json_str)
            output.raw_json = data
            
            # Extract metrics from JSON
            if 'performance' in data:
                perf = data['performance']
                output.total_cycles = perf.get('total_cycles', 0.0)
                output.arithmetic_cycles = perf.get('arithmetic_cycles', 0.0)
                output.load_store_cycles = perf.get('load_store_cycles', 0.0)
                output.texture_cycles = perf.get('texture_cycles', 0.0)
                output.varying_cycles = perf.get('varying_cycles', 0.0)
            
            if 'registers' in data:
                regs = data['registers']
                output.work_registers = regs.get('work', 0)
                output.uniform_registers = regs.get('uniform', 0)
                output.stack_spilling = regs.get('stack_spilling', False)
            
            if 'instructions' in data:
                instr = data['instructions']
                output.total_instructions = instr.get('total', 0)
                output.arithmetic_instructions = instr.get('arithmetic', 0)
                output.load_store_instructions = instr.get('load_store', 0)
                output.texture_instructions = instr.get('texture', 0)
                output.branch_instructions = instr.get('branch', 0)
            
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse malioc JSON output: {e}")
        
        return output


def find_malioc() -> Optional[str]:
    """Convenience function to find malioc executable.
    
    Returns:
        Path to malioc, or None if not found
    """
    runner = MaliocRunner()
    return runner.get_path()


def is_malioc_available() -> bool:
    """Convenience function to check if malioc is available.
    
    Returns:
        True if malioc is installed and executable
    """
    runner = MaliocRunner()
    return runner.is_available()
