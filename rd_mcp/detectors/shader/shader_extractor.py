# rd_mcp/detectors/shader/shader_extractor.py
"""Shader source code extractor from RDC files.

This module provides functionality to extract GLSL/SPIR-V shader source
code from RenderDoc capture files for analysis by malioc or other tools.
"""

import logging
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from rd_mcp.rdc_analyzer_cmd import ShaderInfo, find_renderdoccmd

logger = logging.getLogger(__name__)


@dataclass
class ExtractedShader:
    """Represents an extracted shader with its source and metadata."""
    name: str
    stage: str  # Vertex, Fragment, Compute, etc.
    source: str
    source_language: str = "GLSL"  # GLSL, SPIR-V, HLSL
    entry_point: str = "main"
    
    # Additional metadata
    resource_id: str = ""
    file_path: Optional[Path] = None
    
    # Extraction info
    extraction_method: str = ""  # "xml", "api", "renderdoccmd"
    
    @property
    def has_source(self) -> bool:
        """Check if shader has valid source code."""
        return bool(self.source and len(self.source.strip()) > 0)
    
    @property
    def line_count(self) -> int:
        """Get number of lines in shader source."""
        if not self.source:
            return 0
        return self.source.count('\n') + 1
    
    def to_shader_info(self) -> ShaderInfo:
        """Convert to ShaderInfo for compatibility."""
        return ShaderInfo(
            name=self.name,
            stage=self.stage,
            instruction_count=0,  # Not available without compilation
            source_length=len(self.source) if self.source else 0,
            source=self.source
        )


class ShaderExtractor:
    """Extracts shader source code from RDC files.
    
    Provides multiple methods for shader extraction:
    1. From XML conversion output (already parsed in rdc_analyzer_cmd)
    2. Using renderdoccmd --extract-shaders
    3. From RenderDoc Python API (if available)
    
    Example:
        >>> extractor = ShaderExtractor()
        >>> shaders = extractor.extract_from_rdc("capture.rdc")
        >>> for shader in shaders:
        ...     print(f"{shader.name}: {shader.line_count} lines")
    """
    
    def __init__(self, renderdoccmd_path: Optional[str] = None):
        """Initialize the shader extractor.
        
        Args:
            renderdoccmd_path: Optional path to renderdoccmd executable
        """
        self._renderdoccmd = renderdoccmd_path or find_renderdoccmd()
        self._temp_dirs: List[tempfile.TemporaryDirectory] = []
    
    def __del__(self):
        """Cleanup temporary directories."""
        for temp_dir in self._temp_dirs:
            try:
                temp_dir.cleanup()
            except Exception:
                pass
    
    def extract_from_rdc(
        self,
        rdc_path: str | Path,
        method: str = "auto"
    ) -> List[ExtractedShader]:
        """Extract shaders from an RDC file.
        
        Args:
            rdc_path: Path to the RDC capture file
            method: Extraction method - "auto", "xml", "cmd"
            
        Returns:
            List of extracted shaders
        """
        rdc_path = Path(rdc_path)
        if not rdc_path.exists():
            raise FileNotFoundError(f"RDC file not found: {rdc_path}")
        
        if method == "auto":
            # Try different methods in order of preference
            shaders = self._extract_via_cmd(rdc_path)
            if not shaders:
                shaders = self._extract_via_xml(rdc_path)
            return shaders
        elif method == "cmd":
            return self._extract_via_cmd(rdc_path)
        elif method == "xml":
            return self._extract_via_xml(rdc_path)
        else:
            raise ValueError(f"Unknown extraction method: {method}")
    
    def extract_from_shader_dict(
        self,
        shaders: Dict[str, ShaderInfo]
    ) -> List[ExtractedShader]:
        """Convert ShaderInfo dictionary to ExtractedShader list.
        
        This is useful when shaders have already been parsed from XML.
        
        Args:
            shaders: Dictionary mapping shader names to ShaderInfo
            
        Returns:
            List of ExtractedShader objects
        """
        result = []
        for name, info in shaders.items():
            if info.source:
                result.append(ExtractedShader(
                    name=name,
                    stage=info.stage,
                    source=info.source,
                    source_language="GLSL",
                    extraction_method="xml"
                ))
        return result
    
    def _extract_via_cmd(self, rdc_path: Path) -> List[ExtractedShader]:
        """Extract shaders using renderdoccmd.
        
        Uses the --extract-shaders option if available.
        
        Args:
            rdc_path: Path to RDC file
            
        Returns:
            List of extracted shaders
        """
        if not self._renderdoccmd:
            logger.warning("renderdoccmd not found, cannot extract shaders via cmd")
            return []
        
        # Create temp directory for extracted shaders
        temp_dir = tempfile.TemporaryDirectory()
        self._temp_dirs.append(temp_dir)
        output_dir = Path(temp_dir.name)
        
        try:
            # Try to extract shaders
            # Note: Not all versions of renderdoccmd support this
            cmd = [
                self._renderdoccmd,
                "cap2json",  # Use cap2json which includes shader source
                str(rdc_path),
                "-o", str(output_dir / "capture.json")
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                encoding='utf-8',
                errors='ignore'
            )
            
            if result.returncode != 0:
                logger.debug(f"renderdoccmd cap2json failed: {result.stderr}")
                return []
            
            # Parse the JSON output
            json_path = output_dir / "capture.json"
            if json_path.exists():
                return self._parse_cap2json(json_path)
            
        except subprocess.TimeoutExpired:
            logger.warning("renderdoccmd shader extraction timed out")
        except Exception as e:
            logger.debug(f"Failed to extract shaders via cmd: {e}")
        
        return []
    
    def _extract_via_xml(self, rdc_path: Path) -> List[ExtractedShader]:
        """Extract shaders by parsing XML conversion.
        
        Args:
            rdc_path: Path to RDC file
            
        Returns:
            List of extracted shaders
        """
        try:
            from rd_mcp.rdc_analyzer_cmd import RDCAnalyzerCMD
            
            analyzer = RDCAnalyzerCMD(self._renderdoccmd)
            data = analyzer.analyze_file(rdc_path)
            
            return self.extract_from_shader_dict(data.shaders)
            
        except Exception as e:
            logger.warning(f"Failed to extract shaders via XML: {e}")
            return []
    
    def _parse_cap2json(self, json_path: Path) -> List[ExtractedShader]:
        """Parse cap2json output to extract shaders.
        
        Args:
            json_path: Path to JSON file
            
        Returns:
            List of extracted shaders
        """
        import json
        
        shaders = []
        
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Navigate the JSON structure to find shader sources
            # The exact structure depends on the RenderDoc version
            if 'shaders' in data:
                for shader_id, shader_data in data['shaders'].items():
                    source = shader_data.get('source', '')
                    stage = shader_data.get('stage', 'Unknown')
                    name = shader_data.get('name', f'Shader_{shader_id}')
                    
                    if source:
                        shaders.append(ExtractedShader(
                            name=name,
                            stage=self._normalize_stage(stage),
                            source=source,
                            source_language="GLSL",
                            resource_id=shader_id,
                            extraction_method="cap2json"
                        ))
            
            # Also check for programs/pipelines which may contain shaders
            if 'pipelines' in data:
                for pipeline_id, pipeline_data in data['pipelines'].items():
                    for stage_name, stage_data in pipeline_data.items():
                        if isinstance(stage_data, dict) and 'source' in stage_data:
                            shaders.append(ExtractedShader(
                                name=f"Pipeline_{pipeline_id}_{stage_name}",
                                stage=self._normalize_stage(stage_name),
                                source=stage_data['source'],
                                source_language="GLSL",
                                extraction_method="cap2json"
                            ))
            
        except Exception as e:
            logger.warning(f"Failed to parse cap2json output: {e}")
        
        return shaders
    
    def _normalize_stage(self, stage: str) -> str:
        """Normalize shader stage name.
        
        Args:
            stage: Raw stage name from RDC data
            
        Returns:
            Normalized stage name (Vertex, Fragment, Compute, etc.)
        """
        stage_lower = stage.lower()
        
        if 'vert' in stage_lower:
            return 'Vertex'
        elif 'frag' in stage_lower or 'pixel' in stage_lower:
            return 'Fragment'
        elif 'comp' in stage_lower:
            return 'Compute'
        elif 'geom' in stage_lower:
            return 'Geometry'
        elif 'tess' in stage_lower and 'control' in stage_lower:
            return 'TessControl'
        elif 'tess' in stage_lower and 'eval' in stage_lower:
            return 'TessEvaluation'
        else:
            return stage.capitalize()
    
    def save_shaders_to_directory(
        self,
        shaders: List[ExtractedShader],
        output_dir: str | Path
    ) -> Dict[str, Path]:
        """Save extracted shaders to a directory.
        
        Args:
            shaders: List of extracted shaders
            output_dir: Directory to save shaders
            
        Returns:
            Dictionary mapping shader names to file paths
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        saved_paths = {}
        
        stage_extensions = {
            'Vertex': '.vert',
            'Fragment': '.frag',
            'Compute': '.comp',
            'Geometry': '.geom',
            'TessControl': '.tesc',
            'TessEvaluation': '.tese',
        }
        
        for shader in shaders:
            if not shader.has_source:
                continue
            
            # Generate filename
            safe_name = re.sub(r'[^\w\-_]', '_', shader.name)
            extension = stage_extensions.get(shader.stage, '.glsl')
            filename = f"{safe_name}{extension}"
            
            # Handle duplicates
            file_path = output_dir / filename
            counter = 1
            while file_path.exists():
                filename = f"{safe_name}_{counter}{extension}"
                file_path = output_dir / filename
                counter += 1
            
            # Write shader source
            with open(file_path, 'w', encoding='utf-8') as f:
                # Add metadata header
                f.write(f"// Shader: {shader.name}\n")
                f.write(f"// Stage: {shader.stage}\n")
                f.write(f"// Language: {shader.source_language}\n")
                f.write(f"// Extraction Method: {shader.extraction_method}\n")
                f.write("// " + "=" * 60 + "\n\n")
                f.write(shader.source)
            
            saved_paths[shader.name] = file_path
            shader.file_path = file_path
        
        return saved_paths


def extract_shaders_from_rdc(
    rdc_path: str | Path,
    renderdoccmd_path: Optional[str] = None
) -> List[ExtractedShader]:
    """Convenience function to extract shaders from an RDC file.
    
    Args:
        rdc_path: Path to the RDC capture file
        renderdoccmd_path: Optional path to renderdoccmd
        
    Returns:
        List of extracted shaders
        
    Example:
        >>> shaders = extract_shaders_from_rdc("capture.rdc")
        >>> for s in shaders:
        ...     print(f"{s.stage}: {s.name} ({s.line_count} lines)")
    """
    extractor = ShaderExtractor(renderdoccmd_path)
    return extractor.extract_from_rdc(rdc_path)
