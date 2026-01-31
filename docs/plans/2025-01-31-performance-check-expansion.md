# 性能检查配置扩展设计文档

**日期:** 2025-01-31
**版本:** 1.0
**作者:** Claude & 用户协作

---

## 1. 概述

### 1.1 目标

扩展 RenderDoc MCP 服务器的性能检查配置，支持**移动端和PC游戏优化**，检测以下关键指标：

- Pass 渲染耗时
- Overdraw（实验性）
- Draw Call 数量
- 面数过多的模型
- Fragment/Vertex Shader 复杂度和指令数
- 分析深度/Early-Z 是否生效
- 纹理格式和带宽压力
- Pass/Framebuffer 切换次数

### 1.2 核心原则

1. **只报告问题，不提供建议** - 专注于数据准确性
2. **分阶段实现** - 先实现 XML 可获取指标，高级指标标记为实验性
3. **按检测目标分组** - Geometry、Shader、Pass、Memory 模块化组织
4. **扁平化问题列表** - 按严重程度排序，快速定位瓶颈
5. **混合配置方式** - 提供预设，允许用户自定义覆盖

---

## 2. 配置架构

### 2.1 预设配置

提供移动端和PC端的预设配置文件：

```
rd_mcp/presets/
├── mobile-aggressive.json   # 移动端激进（严格阈值）
├── mobile-balanced.json     # 移动端平衡
└── pc-balanced.json         # PC端平衡
```

**示例配置 (mobile-aggressive.json):**
```json
{
  "description": "移动端激进性能优化 - 严格阈值",
  "thresholds": {
    "geometry": {
      "max_draw_calls": 500,
      "max_triangles": 50000,
      "max_triangles_per_model": 10000
    },
    "shader": {
      "max_vs_instructions": 100,
      "max_fs_instructions": 150
    },
    "pass": {
      "max_duration_ms": 0.3,
      "max_overdraw_ratio": 2.0,
      "max_switches_per_frame": 8
    },
    "memory": {
      "max_texture_size": 2048,
      "require_compressed_textures": true
    }
  }
}
```

### 2.2 用户配置覆盖

用户可以在 `config.json` 中覆盖预设值：

```json
{
  "preset": "mobile-aggressive",
  "thresholds": {
    "geometry": {
      "max_triangles": 80000  // 覆盖预设值
    }
  }
}
```

### 2.3 阈值数据类重构

```python
@dataclass
class GeometryThresholds:
    max_triangles: int = 100000
    max_draw_calls: int = 1000
    max_triangles_per_model: int = 50000

@dataclass
class ShaderThresholds:
    max_vs_instructions: int = 500
    max_fs_instructions: int = 500
    max_cs_instructions: int = 1000

@dataclass
class PassThresholds:
    max_duration_ms: float = 1.0
    max_overdraw_ratio: float = 2.5
    max_switches_per_frame: int = 20

@dataclass
class MemoryThresholds:
    max_texture_size: int = 4096
    require_compressed_textures: bool = False
```

---

## 3. 检测器架构

### 3.1 目录结构

```
rd_mcp/detectors/
├── base.py                    # 检测器基类
├── geometry/
│   ├── drawcall.py            # Draw Call 数量（现有）
│   ├── triangle_count.py      # 三角形数量（新增）
│   └── model_stats.py         # 模型统计（新增）
├── shader/
│   ├── instruction_count.py   # 指令数（现有）
│   ├── complexity.py          # 复杂度分析（新增）
│   └── mali_complexity.py      # Mali OC 分析（新增）
├── pass/
│   ├── duration.py            # Pass 耗时（新增）
│   └── switches.py            # 状态切换（新增）
└── memory/
    ├── texture_size.py        # 纹理大小（新增）
    └── texture_format.py      # 格式检测（新增）
```

### 3.2 检测器基类

```python
# rd_mcp/detectors/base.py
from abc import ABC, abstractmethod

class BaseDetector(ABC):
    """所有检测器的基类"""

    def __init__(self, thresholds: Dict[str, Any]):
        self.thresholds = thresholds

    @abstractmethod
    def detect(self, data: Any) -> List[Issue]:
        """执行检测，返回问题列表"""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """检测器名称"""
        pass
```

### 3.3 新增检测器清单

| 模块 | 检测器 | 功能 | 优先级 |
|------|--------|------|--------|
| Geometry | triangle_count | 三角形总数检测 | P0 |
| Geometry | model_stats | 单个模型统计 | P0 |
| Shader | mali_complexity | Mali OC 分析 | P0 |
| Shader | complexity | 复杂度分析 | P1 |
| Pass | duration | Pass 耗时检测 | P0 |
| Pass | switches | 状态切换检测 | P1 |
| Memory | texture_size | 纹理大小估算 | P1 |
| Memory | texture_format | 格式检测 | P2 |

---

## 4. 数据模型扩展

### 4.1 模型统计数据

```python
@dataclass
class ModelStats:
    """单个模型/资源的统计信息"""
    name: str
    draw_calls: int = 0
    triangle_count: int = 0
    vertex_count: int = 0
    passes: List[str] = field(default_factory=list)
```

### 4.2 分析结果扩展

```python
@dataclass
class AnalysisResult:
    summary: ReportSummary
    issues: Dict[str, List[Issue]]
    metrics: Dict[str, Any]
    errors: List[str]  # 新增：检测过程中的错误
```

### 4.3 Pass 切换详细数据

```python
@dataclass
class PassSwitchInfo:
    """Pass/Framebuffer 切换详情"""
    marker_switches: int      # Pass 标记切换
    fbo_switches: int          # FBO 切换
    texture_bind_changes: int # 纹理绑定改变
    shader_changes: int       # Shader 切换
    total: int                # 总计
```

---

## 5. 关键实现细节

### 5.1 模型统计提取

按模型/资源分类统计 Draw Call 和三角形：

```python
def _extract_model_stats(self, draws: List[DrawCallInfo]) -> Dict[str, ModelStats]:
    """从 Draw Call 提取模型统计"""
    models = {}

    for draw in draws:
        # 智能推断模型名称
        model_name = self._infer_model_name(draw)

        # 累积统计
        if model_name not in models:
            models[model_name] = ModelStats(name=model_name)

        stats = models[model_name]
        stats.draw_calls += 1
        stats.triangle_count += draw.vertex_count // 3
        stats.vertex_count += draw.vertex_count

    return models

def _infer_model_name(self, draw: DrawCallInfo) -> str:
    """智能推断模型名称"""
    # 规则1: 优先使用 marker
    if draw.marker:
        return draw.marker

    # 规则2: 从 name 提取
    if "Model" in draw.name:
        parts = draw.name.split("_")
        if len(parts) > 1:
            return parts[1]

    # 规则3: 从绑定资源名
    # 规则4: 从着色器名推断
    # 规则5: 默认分组

    return "Unknown"
```

### 5.2 Mali OC 集成

自动调用 Mali Offline Compiler 分析 Shader：

```python
# rd_mcp/detectors/shader/mali_complexity.py
class MaliComplexityDetector(BaseDetector):
    def __init__(self, thresholds: Dict, malioc_path="malioc"):
        self.malioc_path = malioc_path
        self.max_cycles = thresholds.get("max_cycles", 1000)

    def detect(self, shaders: Dict[str, ShaderInfo]) -> List[Issue]:
        issues = []

        for shader_name, shader_info in shaders.items():
            # 写入临时文件
            temp_file = self._write_temp_shader(shader_info)

            # 调用 Mali OC
            report = self._run_malioc(temp_file, shader_info.stage)

            # 解析核心指标
            if report["cycles"] > self.max_cycles:
                issues.append(Issue(
                    type="expensive_shader_mali",
                    severity=IssueSeverity.CRITICAL,
                    description=f"{shader_name} Mali 周期数: {report['cycles']}",
                    location=f"Shader: {shader_name}",
                    impact="high"
                ))

        return issues

    def _run_malioc(self, shader_path: str, stage: str) -> Dict:
        """运行 Mali OC 并解析输出"""
        cmd = [
            self.malioc_path,
            "--shader-stage", stage,
            "--text",
            shader_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return self._parse_malioc_output(result.stdout)
```

### 5.3 Pass 切换层级检测

```python
def detect_pass_switches_detailed(self, draws: List[DrawCallInfo]) -> Dict[str, int]:
    """层级检测：区分多种切换类型"""
    marker_switches = 0
    fbo_switches = 0
    texture_bind_changes = 0
    shader_changes = 0

    last_marker = None
    last_fbo = None
    last_textures = set()
    last_shader = None

    for draw in draws:
        # Marker 切换
        if draw.marker != last_marker:
            marker_switches += 1
            last_marker = draw.marker

        # FBO 切换
        current_fbo = self._extract_fbo(draw)
        if current_fbo != last_fbo:
            fbo_switches += 1
            last_fbo = current_fbo

        # 纹理绑定切换
        current_textures = self._extract_bound_textures(draw)
        if current_textures != last_textures:
            texture_bind_changes += len(current_textures ^ last_textures)
            last_textures = current_textures

        # Shader 切换
        current_shader = self._get_shader_name(draw)
        if current_shader != last_shader:
            shader_changes += 1
            last_shader = current_shader

    return {
        "marker_switches": marker_switches,
        "fbo_switches": fbo_switches,
        "texture_bind_changes": texture_bind_changes,
        "shader_changes": shader_changes
    }
```

### 5.4 Overdraw 估算（实验性）

标记为实验性功能，使用启发式估算：

```python
def estimate_overdraw_risk(draws: List[DrawCallInfo]) -> Dict[str, float]:
    """估算 Overdraw 风险"""
    pass_risks = {}

    for draw in draws:
        risk = 0.0

        # 基于特征估算
        if "FullScreen" in draw.name and "Transparent" in draw.marker:
            risk += 2.0
        if "Layer" in draw.name:
            risk += 1.5
        if "Particle" in draw.name:
            risk += 3.0

        pass_risks[draw.marker or "Unknown"] = risk

    return pass_risks
```

### 5.5 纹理大小估算

计算纹理内存占用，量化带宽压力：

```python
def estimate_texture_size(texture: TextureInfo) -> int:
    """估算纹理内存占用（字节）"""
    pixel_count = texture.width * texture.height

    # 格式到 BPP 映射
    bpp_map = {
        "RGBA8": 4, "RGB8": 3,
        "ASTC4x4": 0.5, "ETC2": 0.5,
        "BC7": 0.5, "BC1": 0.5
    }

    format_upper = texture.format.upper()
    bpp = 4  # 默认
    for fmt, size in bpp_map.items():
        if fmt in format_upper:
            bpp = size
            break

    return int(pixel_count * bpp * texture.mips * texture.array_size)
```

---

## 6. 报告格式

### 6.1 输出结构

```
# GPU 性能分析报告

## 摘要
- API: OpenGL ES 3.2
- 总耗时: 16.70ms
- Draw Calls: 922
- 三角形: 1,245,680

## 问题总数: 8

## 🔴 严重问题 (3)

1. **excessive_triangles**
   描述: 三角形数量过多 (1,245,680)，超过阈值 100,000
   位置: Frame
   影响: high

2. **slow_pass**
   描述: Pass 'ShadowPass' 耗时 5.20ms，超过阈值 0.50ms
   位置: Pass: ShadowPass (2048x2048)
   影响: high

3. **expensive_shader_mali**
   描述: lighting_ps Mali 周期数: 1250
   位置: Shader: lighting_ps
   影响: high

## ⚠️ 警告 (4)

1. **texture_uncompressed**
   描述: 纹理 albedo_map (2048x2048) 未压缩
   位置: Resource: albedo_map
   影响: medium

2. **pass_switches**
   描述: Pass/Framebuffer 切换 25次，超过阈值 10次
   位置: Frame
   影响: medium

3. **heavy_model**
   描述: 模型 'Character_Hero' 三角形 450,000
   位置: Model: Character_Hero (120 Draw Calls)
   影响: medium

4. **experimental_overdraw**
   描述: Transparent Pass 估算 Overdraw 3.2x（实验性）
   位置: Pass: Transparent Pass
   影响: medium

## 📊 模型统计

### Character_Hero
- Draw Calls: 120
- 三角形: 450,000 (36.1%)
- 顶点: 150,000
- 出现于: Geometry Pass, Shadow Pass

[...]

## ⚠️ 检测错误

- model_stats: 部分模型无法识别，归为 Unknown
- mali_complexity: 使用回退方法（Mali OC 不可用）
```

---

## 7. 错误处理

### 7.1 详细错误报告

在 `AnalysisResult` 中新增 `errors` 字段：

```python
@dataclass
class AnalysisResult:
    summary: ReportSummary
    issues: Dict[str, List[Issue]]
    metrics: Dict[str, Any]
    errors: List[str]  # 检测过程中的错误信息
```

### 7.2 部分容错逻辑

```python
CRITICAL_DETECTORS = {"triangle_count", "pass_duration"}
OPTIONAL_DETECTORS = {"model_stats", "shader_complexity", "overdraw"}

def analyze(self, ...):
    issues = []
    errors = []

    for detector in self.all_detectors:
        try:
            detected = detector.detect(data)
            issues.extend(detected)
        except Exception as e:
            if detector.name in CRITICAL_DETECTORS:
                raise RuntimeError(f"关键检测 {detector.name} 失败: {e}")
            else:
                errors.append(f"{detector.name}: {str(e)}")

    return AnalysisResult(
        summary=summary,
        issues=issues,
        metrics=metrics,
        errors=errors
    )
```

---

## 8. 实施优先级

### 第一阶段 (P0) - 核心功能
- [ ] 配置系统重构（预设 + 覆盖）
- [ ] 检测器基类和模块化组织
- [ ] triangle_count 检测器
- [ ] model_stats 检测器
- [ ] Pass duration 检测器
- [ ] Mali complexity 基础集成

### 第二阶段 (P1) - 增强功能
- [ ] Pass switches 检测器
- [ ] Shader complexity 检测器
- [ ] Texture size 估算
- [ ] 模型统计报告输出

### 第三阶段 (P2) - 高级功能
- [ ] Texture format 检测
- [ ] Overdraw 估算（实验性）
- [ ] Early-Z 检测（标记为 TODO）

---

## 9. 测试策略

### 9.1 单元测试

```
rd_mcp/tests/
├── detectors/
│   ├── test_geometry_detectors.py
│   ├── test_shader_detectors.py
│   ├── test_pass_detectors.py
│   └── test_memory_detectors.py
└── fixtures/
    ├── rdc_samples/
    │   ├── mobile_game.xml
    │   └── pc_game.xml
    └── expected/
        ├── mobile_aggressive_output.json
        └── pc_balanced_output.json
```

### 9.2 集成测试

- [ ] 完整分析流程测试（RDC → 分析 → 报告）
- [ ] 预设配置加载测试
- [ ] 配置覆盖测试
- [ ] 错误处理测试

---

## 10. 依赖项

### 10.1 新增依赖

```python
# rd_mcp/requirements.txt
mcp>=0.1.0
beautifulsoup4>=4.12.0
lxml>=5.0.0
pydantic>=2.0.0
pytest>=7.4.0
pytest-cov>=4.1.0

# Mali Offline Compiler (外部依赖)
# 需要单独安装 ARM GPU Analyzer
```

### 10.2 Mali OC 安装

用户需要安装 Mali GPU Analyzer：
- 下载地址：https://developer.arm.com/tools-and-software/graphics-and-gaming/arm-mali-gpu-developer-tools

---

## 11. 风险与限制

### 11.1 数据源限制

使用 `renderdoccmd` XML 输出限制了一些高级指标的精确获取：
- **Overdraw**: 只能估算，无法获取实际像素统计
- **Early-Z**: XML 中无深度测试详细信息
- **带宽压力**: 只能通过纹理大小估算

### 11.2 Mali OC 依赖

- 需要用户单独安装 Mali GPU Analyzer
- 不可用时需要回退到简化检测

### 11.3 性能考虑

- XML 解析可能较慢（大文件）
- Mali OC 调用增加分析时间
- 建议：提供缓存机制

---

## 12. 未来扩展

### 12.1 第二阶段功能（需要完整 RenderDoc API）

- Overdraw 精确检测
- Early-Z 有效性分析
- 实际带宽测量
- GPU 占用率分析

### 12.2 可视化增强

- 生成 HTML 格式报告
- 添加图表展示趋势
- 交互式问题定位

---

**文档版本:** 1.0
**最后更新:** 2025-01-31
