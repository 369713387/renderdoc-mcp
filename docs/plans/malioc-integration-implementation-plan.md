# Mali Offline Compiler (malioc) 集成实现计划

**创建日期**: 2025-01-31  
**状态**: 待实现  
**优先级**: P0 (核心功能)

---

## 1. 概述

### 1.1 目标
集成 ARM Mali Offline Compiler (malioc) 到 RenderDoc MCP 框架中，提供精确的 Mali GPU Shader 复杂度分析，包括：
- GPU 周期数 (Cycles)
- 寄存器压力 (Register Pressure)
- 指令分布 (Arithmetic/Load/Store/Texture)
- 最短/最长路径分析

### 1.2 背景
当前 Shader 分析只基于简单的指令数统计（`instruction_count`），无法反映 Mali GPU 上的真实性能表现。malioc 提供的分析数据对移动端优化至关重要。

---

## 2. 架构设计

### 2.1 新增文件结构

```
rd_mcp/
├── detectors/
│   └── shader/                     # 新增目录
│       ├── __init__.py
│       ├── mali_complexity.py      # Mali OC 检测器
│       └── shader_source.py        # Shader 源码提取工具
├── config.py                       # 更新：添加 malioc 配置
└── presets/
    ├── mobile-aggressive.json      # 更新：添加 Mali 阈值
    └── mobile-balanced.json        # 更新：添加 Mali 阈值
```

### 2.2 类图

```
BaseDetector
     │
     ├── ShaderDetector (现有)
     │       └── detect_expensive_shaders()
     │
     └── MaliComplexityDetector (新增)
             ├── detect(shaders: Dict) -> List[Issue]
             ├── _find_malioc() -> Optional[str]
             ├── _run_malioc(shader_path, stage) -> MaliReport
             ├── _parse_output(stdout) -> MaliReport
             └── _write_temp_shader(source, stage) -> str
```

---

## 3. 详细实现方案

### 3.1 MaliComplexityDetector 类

```python
# rd_mcp/detectors/shader/mali_complexity.py

from dataclasses import dataclass
from typing import Dict, List, Optional
import subprocess
import tempfile
import os
import re
from pathlib import Path

from rd_mcp.detectors.base import BaseDetector
from rd_mcp.models import Issue, IssueSeverity


@dataclass
class MaliReport:
    """Mali OC 分析报告数据"""
    cycles_total: float = 0.0       # 总周期数
    cycles_arithmetic: float = 0.0  # 算术周期
    cycles_load_store: float = 0.0  # 读写周期
    cycles_texture: float = 0.0     # 纹理采样周期
    register_count: int = 0         # 寄存器使用数
    shortest_path: float = 0.0      # 最短路径周期
    longest_path: float = 0.0       # 最长路径周期
    has_divergent_flow: bool = False  # 是否有分支发散
    raw_output: str = ""            # 原始输出


class MaliComplexityDetector(BaseDetector):
    """Mali GPU Shader 复杂度检测器"""
    
    # malioc 可能的安装路径
    MALIOC_PATHS = [
        r"C:\Program Files\Arm\Arm Mobile Studio\Mali Offline Compiler\malioc.exe",
        r"C:\Program Files\ARM\Mali Developer Tools\Mali Offline Compiler\malioc.exe",
        "/usr/bin/malioc",
        "/usr/local/bin/malioc",
    ]
    
    # Stage 映射
    STAGE_MAP = {
        "VS": "vertex",
        "PS": "fragment", 
        "FS": "fragment",
        "CS": "compute",
        "vertex": "vertex",
        "fragment": "fragment",
        "compute": "compute",
    }

    def __init__(self, thresholds: Dict, malioc_path: Optional[str] = None):
        super().__init__(thresholds)
        self.malioc_path = malioc_path or self._find_malioc()
        self.max_cycles = thresholds.get("max_mali_cycles", 1000)
        self.max_registers = thresholds.get("max_mali_registers", 32)
        self.enabled = self.malioc_path is not None
    
    @property
    def name(self) -> str:
        return "mali_complexity"
    
    def _find_malioc(self) -> Optional[str]:
        """查找 malioc 可执行文件"""
        # 检查环境变量
        env_path = os.environ.get("MALIOC_PATH")
        if env_path and Path(env_path).exists():
            return env_path
        
        # 检查预定义路径
        for path in self.MALIOC_PATHS:
            if Path(path).exists():
                return path
        
        return None
    
    def detect(self, shaders: Dict[str, "ShaderInfo"]) -> List[Issue]:
        """检测 Shader 复杂度问题"""
        issues = []
        
        if not self.enabled:
            # malioc 不可用，返回警告
            return [Issue(
                type="mali_complexity_unavailable",
                severity=IssueSeverity.SUGGESTION,
                description="Mali Offline Compiler 不可用，跳过 GPU 周期分析",
                location="System",
                impact="low"
            )]
        
        for shader_name, shader_info in shaders.items():
            # 跳过没有源码的 shader
            if not hasattr(shader_info, 'source') or not shader_info.source:
                continue
            
            try:
                report = self._analyze_shader(shader_info)
                
                # 检查周期数
                if report.cycles_total > self.max_cycles:
                    issues.append(Issue(
                        type="expensive_shader_mali",
                        severity=IssueSeverity.CRITICAL,
                        description=(
                            f"Shader '{shader_name}' Mali 周期数过高 "
                            f"({report.cycles_total:.1f} cycles)，"
                            f"超过阈值 {self.max_cycles}"
                        ),
                        location=f"Shader: {shader_name}",
                        impact="high",
                        details={
                            "cycles_arithmetic": report.cycles_arithmetic,
                            "cycles_load_store": report.cycles_load_store,
                            "cycles_texture": report.cycles_texture,
                            "registers": report.register_count
                        }
                    ))
                
                # 检查寄存器压力
                if report.register_count > self.max_registers:
                    issues.append(Issue(
                        type="shader_register_pressure",
                        severity=IssueSeverity.WARNING,
                        description=(
                            f"Shader '{shader_name}' 寄存器压力过高 "
                            f"({report.register_count} registers)，"
                            f"可能导致 spilling"
                        ),
                        location=f"Shader: {shader_name}",
                        impact="medium"
                    ))
                
                # 检查分支发散
                if report.has_divergent_flow:
                    issues.append(Issue(
                        type="shader_divergent_flow",
                        severity=IssueSeverity.WARNING,
                        description=(
                            f"Shader '{shader_name}' 存在分支发散，"
                            f"最短路径 {report.shortest_path:.1f} vs "
                            f"最长路径 {report.longest_path:.1f} cycles"
                        ),
                        location=f"Shader: {shader_name}",
                        impact="medium"
                    ))
                    
            except Exception as e:
                # 单个 shader 分析失败不影响其他
                issues.append(Issue(
                    type="mali_analysis_error",
                    severity=IssueSeverity.SUGGESTION,
                    description=f"Shader '{shader_name}' Mali 分析失败: {str(e)}",
                    location=f"Shader: {shader_name}",
                    impact="low"
                ))
        
        return issues
    
    def _analyze_shader(self, shader_info) -> MaliReport:
        """分析单个 Shader"""
        # 写入临时文件
        stage = self.STAGE_MAP.get(shader_info.stage, "fragment")
        temp_path = self._write_temp_shader(shader_info.source, stage)
        
        try:
            # 运行 malioc
            return self._run_malioc(temp_path, stage)
        finally:
            # 清理临时文件
            if os.path.exists(temp_path):
                os.remove(temp_path)
    
    def _write_temp_shader(self, source: str, stage: str) -> str:
        """写入临时 Shader 文件"""
        suffix = ".frag" if stage == "fragment" else ".vert" if stage == "vertex" else ".comp"
        
        with tempfile.NamedTemporaryFile(
            mode='w', 
            suffix=suffix, 
            delete=False,
            encoding='utf-8'
        ) as f:
            f.write(source)
            return f.name
    
    def _run_malioc(self, shader_path: str, stage: str) -> MaliReport:
        """运行 Mali Offline Compiler"""
        cmd = [
            self.malioc_path,
            "--" + stage,
            "--core", "Mali-G78",  # 目标 GPU 核心
            shader_path
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"malioc failed: {result.stderr}")
        
        return self._parse_output(result.stdout)
    
    def _parse_output(self, stdout: str) -> MaliReport:
        """解析 malioc 输出"""
        report = MaliReport(raw_output=stdout)
        
        # 解析周期数
        # 典型输出格式:
        # Total instruction cycles:       12.50
        # Shortest path cycles:           10.00
        # Longest path cycles:            15.00
        # A = Arithmetic, LS = Load/Store, T = Texture
        
        patterns = {
            'cycles_total': r'Total instruction cycles:\s*(\d+\.?\d*)',
            'cycles_arithmetic': r'Arithmetic:\s*(\d+\.?\d*)',
            'cycles_load_store': r'Load/Store:\s*(\d+\.?\d*)',
            'cycles_texture': r'Texture:\s*(\d+\.?\d*)',
            'shortest_path': r'Shortest path cycles:\s*(\d+\.?\d*)',
            'longest_path': r'Longest path cycles:\s*(\d+\.?\d*)',
            'register_count': r'Work registers:\s*(\d+)',
        }
        
        for field, pattern in patterns.items():
            match = re.search(pattern, stdout, re.IGNORECASE)
            if match:
                value = float(match.group(1)) if '.' in match.group(1) or field != 'register_count' else int(match.group(1))
                setattr(report, field, value)
        
        # 检查分支发散
        if report.shortest_path > 0 and report.longest_path > 0:
            divergence = report.longest_path / report.shortest_path
            report.has_divergent_flow = divergence > 1.5
        
        return report


# 便捷函数
def is_malioc_available() -> bool:
    """检查 malioc 是否可用"""
    detector = MaliComplexityDetector({})
    return detector.enabled
```

### 3.2 配置扩展

```python
# 在 rd_mcp/config.py 中添加

@dataclass
class MaliThresholds:
    """Mali GPU 相关阈值"""
    max_cycles: int = 1000          # 最大周期数
    max_registers: int = 32         # 最大寄存器数
    cycle_divergence_ratio: float = 1.5  # 分支发散阈值
    enabled: bool = True            # 是否启用
    
    def __post_init__(self):
        if self.max_cycles <= 0:
            raise ValueError("max_cycles must be positive")


# 在预设中添加
# mobile-aggressive.json
{
    "thresholds": {
        "mali": {
            "max_cycles": 500,
            "max_registers": 24,
            "enabled": true
        }
    }
}

# mobile-balanced.json  
{
    "thresholds": {
        "mali": {
            "max_cycles": 1000,
            "max_registers": 32,
            "enabled": true
        }
    }
}
```

### 3.3 Shader 源码提取

```python
# rd_mcp/detectors/shader/shader_source.py

"""
Shader 源码提取工具

从 RenderDoc 捕获中提取 Shader 源码的工具类。
支持 GLSL、SPIRV 反编译等格式。
"""

from typing import Optional
from pathlib import Path


class ShaderSourceExtractor:
    """Shader 源码提取器"""
    
    def __init__(self, renderdoc_path: Optional[str] = None):
        self.renderdoc_path = renderdoc_path
    
    def extract_from_rdc(self, rdc_path: str, shader_id: str) -> Optional[str]:
        """从 RDC 文件提取 Shader 源码
        
        注意：需要 RenderDoc Python API (renderdoc module)
        """
        try:
            import renderdoc as rd
            
            controller = rd.OpenCaptureFile()
            status = controller.OpenFile(rdc_path, '', None)
            
            if status != rd.ReplayStatus.Succeeded:
                return None
            
            # 获取 shader 反射信息
            # ... 实现细节
            
            return None  # TODO: 实现
            
        except ImportError:
            # renderdoc module 不可用
            return None
    
    def extract_from_xml(self, xml_path: str, shader_name: str) -> Optional[str]:
        """从 XML 导出中提取 Shader 源码
        
        renderdoccmd 的 XML 输出可能包含 shader 源码
        """
        # XML 格式可能不包含完整源码
        return None
```

---

## 4. 集成到分析流程

### 4.1 Analyzer 更新

```python
# 在 rd_mcp/analyzer.py 中

from rd_mcp.detectors.shader.mali_complexity import MaliComplexityDetector, is_malioc_available

class Analyzer:
    def __init__(self, config_path=None, preset=None):
        # ... 现有代码 ...
        
        # 新增 Mali 检测器
        mali_thresholds = self.config.thresholds.get("mali", {})
        self.mali_detector = MaliComplexityDetector(mali_thresholds)
    
    def analyze(self, summary, shaders, resources, draws=None, passes=None):
        # ... 现有检测逻辑 ...
        
        # Mali 复杂度检测
        if self.mali_detector.enabled:
            try:
                for issue in self.mali_detector.detect(shaders):
                    key = severity_map.get(issue.severity.value)
                    issues[key].append(issue)
            except Exception as e:
                errors.append(f"Mali analysis error: {str(e)}")
```

### 4.2 Server 更新

```python
# 在 rd_mcp/server.py 的 analyze_rdc 函数中

# 提取 shader 源码（如果可用）
shaders_with_source = {}
for name, shader in rdc_data.shaders.items():
    shader_dict = {
        "instruction_count": getattr(shader, 'instruction_count', 0),
        "stage": getattr(shader, 'stage', 'Unknown'),
        "source": getattr(shader, 'source', ''),  # 新增
    }
    shaders_with_source[name] = shader_dict
```

---

## 5. 实施步骤

### Phase 1: 基础框架 (1-2 天)
- [ ] 创建 `rd_mcp/detectors/shader/` 目录
- [ ] 实现 `MaliComplexityDetector` 基础类
- [ ] 实现 malioc 路径查找逻辑
- [ ] 添加单元测试

### Phase 2: 解析器实现 (1 天)
- [ ] 实现 `_parse_output()` 解析 malioc 输出
- [ ] 实现 `_run_malioc()` 调用逻辑
- [ ] 添加超时和错误处理

### Phase 3: 配置集成 (0.5 天)
- [ ] 更新 `config.py` 添加 Mali 阈值
- [ ] 更新预设文件
- [ ] 添加环境变量支持

### Phase 4: 分析流程集成 (0.5 天)
- [ ] 更新 `Analyzer` 类
- [ ] 更新报告输出格式
- [ ] 端到端测试

### Phase 5: 文档和测试 (1 天)
- [ ] 编写用户文档
- [ ] 添加集成测试
- [ ] 性能测试

---

## 6. 测试计划

### 6.1 单元测试

```python
# rd_mcp/tests/detectors/test_mali_complexity.py

import pytest
from rd_mcp.detectors.shader.mali_complexity import (
    MaliComplexityDetector,
    MaliReport,
    is_malioc_available
)


class TestMaliComplexityDetector:
    """Mali 复杂度检测器测试"""
    
    def test_malioc_not_available(self):
        """测试 malioc 不可用时的行为"""
        detector = MaliComplexityDetector({}, malioc_path="/nonexistent")
        assert not detector.enabled
        
        issues = detector.detect({})
        assert len(issues) == 1
        assert issues[0].type == "mali_complexity_unavailable"
    
    def test_parse_output(self):
        """测试输出解析"""
        sample_output = """
        Mali-G78 Performance Analysis
        
        Total instruction cycles:       12.50
        Shortest path cycles:           10.00
        Longest path cycles:            15.00
        
        Work registers: 24
        
        Arithmetic:                     8.00
        Load/Store:                     2.50
        Texture:                        2.00
        """
        
        detector = MaliComplexityDetector({})
        report = detector._parse_output(sample_output)
        
        assert report.cycles_total == 12.5
        assert report.cycles_arithmetic == 8.0
        assert report.register_count == 24
    
    @pytest.mark.skipif(not is_malioc_available(), reason="malioc not installed")
    def test_real_shader_analysis(self):
        """真实 shader 分析测试（需要 malioc）"""
        # 使用简单测试 shader
        pass


class TestMaliReport:
    """MaliReport 数据类测试"""
    
    def test_default_values(self):
        report = MaliReport()
        assert report.cycles_total == 0.0
        assert report.register_count == 0
        assert not report.has_divergent_flow
```

### 6.2 集成测试

```python
# rd_mcp/tests/integration/test_mali_integration.py

@pytest.mark.integration
def test_full_analysis_with_mali():
    """完整分析流程测试（包含 Mali 检测）"""
    # 使用测试 RDC 文件
    pass
```

---

## 7. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| malioc 未安装 | 高 | 提供清晰的降级提示和安装指南 |
| Shader 源码不可用 | 高 | XML 导出可能不包含源码，标记为已知限制 |
| malioc 版本差异 | 中 | 解析器支持多种输出格式 |
| 分析耗时过长 | 中 | 添加超时控制和缓存机制 |

---

## 8. 用户文档

### 8.1 安装 Mali Offline Compiler

1. 下载 ARM Mobile Studio: https://developer.arm.com/tools-and-software/graphics-and-gaming/arm-mobile-studio
2. 安装 Mali Offline Compiler 组件
3. 确保 `malioc` 在 PATH 中，或设置环境变量：
   ```bash
   export MALIOC_PATH=/path/to/malioc
   ```

### 8.2 配置示例

```json
{
  "thresholds": {
    "mali": {
      "max_cycles": 500,
      "max_registers": 24,
      "enabled": true
    }
  }
}
```

---

## 9. 验收标准

- [ ] malioc 可用时，能正确分析 Shader 并报告问题
- [ ] malioc 不可用时，能优雅降级并给出提示
- [ ] 所有预设配置正确加载 Mali 阈值
- [ ] 报告中显示 Mali 分析结果（周期数、寄存器等）
- [ ] 单元测试覆盖率 > 80%
- [ ] 集成测试通过
