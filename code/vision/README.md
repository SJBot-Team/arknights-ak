# vision — 可插拔视觉控制内核（明日方舟 GUI 识别与控制）

> 位置：`ak\code\vision` ｜ 环境：`.venv`（Python 3.13）｜ 设计参考：**MAA**（内核 + 可替换控制器 + 模板/任务分离）与 **赛博塑料 prts+**（JSON 键鼠方案 + 相对坐标）
>
> **核心思想**：内核只提供抽象（采集/识别/动作/流水线），具体能力全在 `plugins/`。
> 换需求（换游戏、换输入方式、换识别算法）时**只替换插件，内核与流水线格式不动**。

## 一、目录结构

```
ak\code\vision\
├── kernel\                     # 内核（稳定，不随需求变化）
│   ├── types.py                # Rect / Frame / Match / ActionSpec / Context
│   ├── registry.py             # 插件注册表（capture / recognizer / action / task）
│   ├── capture.py              # 采集抽象 + 后端选择（失败自动降级）
│   ├── input.py                # 输入抽象 + 动作派发 + 三种坐标写法
│   ├── vision.py               # 模板库（热加载）+ 模板匹配（NMS/多尺度/降采样）
│   ├── window.py               # 窗口定位（标题/PID → 客户区矩形）
│   ├── pipeline.py             # 任务流水线（JSON 定义，识别→动作→跳转）
│   └── engine.py               # 60FPS 主循环、ROI 调度、统计
├── plugins\                    # 插件（换需求改这里）
│   ├── capture\  dxgi_backend.py（bettercam/dxcam）· mss_backend.py（mss/video）
│   ├── recognize\ template_match.py · color.py · ocr.py（PaddleOCR，可选）
│   ├── action\   backends.py（input:directinput / input:sendinput）
│   └── task\     video_analyze.py（场景②：视频操作步骤提取）
├── apps\                       # 入口脚本
│   ├── selftest.py             # 自检（无需窗口/游戏）
│   ├── bench_fps.py            # 性能基准（验证 60FPS）
│   ├── diag_match.py / diag_opencl.py  # 匹配成本诊断
│   ├── run_client.py           # 场景①：识别并操控本地客户端
│   └── analyze_video.py        # 场景②：分析攻略视频
├── pipelines\                  # 任务流水线 JSON（业务逻辑，可随时改）
├── templates\                  # 模板图库（丢 PNG 即新增识别目标）
└── requirements.txt
```

## 二、插件契约（扩展的唯一入口）

| 类型 | 基类/装饰器 | 必须实现 | 举例 |
|---|---|---|---|
| 采集 | `@capture("name")` | `open()` / `grab(region)->Frame` / `close()` | bettercam、mss、video |
| 识别 | `@recognizer("name")` | `run(image, spec, ctx, origin)->list[Match]` | template、color、ocr |
| 动作 | `@action("input:name")` | `click/move/drag/scroll/key/text` | directinput、sendinput |
| 任务 | `@task("name")` | `run(engine)->dict` | video_analyze |

新增能力＝在 `plugins/` 下加一个模块并注册；`engine.open()` 会自动发现并加载（单个插件报错不影响内核）。

```python
# 例：新增"特征点匹配"识别器 → plugins/recognize/feature.py
from kernel.registry import recognizer
from kernel.types import Match

@recognizer("feature")
class FeatureRecognizer:
    def run(self, image, spec, ctx, origin, label="", engine=None):
        ...  # 返回 list[Match]
```

## 三、性能实测（本机：Ryzen 9 7945HX + RTX 4060，1080p，64×64 模板）

| 场景 | 单次耗时 | 折算能力 |
|---|---|---|
| 全帧 1920×1080 模板匹配 | **124 ms** | 8 次/秒 ❌ |
| 全帧 + OpenCL（NVD3D11） | 48 ms | 21 次/秒 |
| 降采样 0.5× | 34 ms | 29 次/秒 |
| 降采样 0.25× | 8.3 ms | 120 次/秒 |
| **ROI 140×140** | **0.87 ms** | **1150 次/秒 ✅** |
| ROI 400×300 + OpenCL | 5.2 ms | 190 次/秒 |
| 多尺度（3 个尺度） | ×3 成本 | 慎用 |
| **抓屏（bettercam/DXGI）** | **0.4 ms** | 6788 FPS（静止画面） |
| 端到端节拍 | — | **60.0 FPS 稳定** |

**结论**：60 FPS 的关键不是算法而是**搜索范围**。
- 实战做法（与 MAA 一致）：**每个流水线节点只在自己小 ROI 内匹配** → 单帧可跑几十个识别点；
- 需要全屏找目标时：先降采样粗定位，再在候选区域原分辨率精匹配。

## 四、用法

```powershell
cd ak\code\vision
.\.venv\Scripts\python.exe apps\selftest.py        # 自检
.\.venv\Scripts\python.exe apps\bench_fps.py       # 性能基准
.\.venv\Scripts\python.exe apps\run_client.py --window "明日方舟" --pipeline pipelines\demo.json --dry-run
.\.venv\Scripts\python.exe apps\analyze_video.py --video "E:\__file\__video\xxx.mp4" --pipeline pipelines\demo.json
```

### 模板（增减识别目标）
把 PNG 丢进 `templates\`（可分子目录，如 `templates\main\start.png` → 模板名 `main/start`），
运行中自动热加载。**可直接复用 MAA 的 2149 张模板**（`D:\__soft\MAA\resource\template\`）：

```powershell
# 按需挑选，不要整目录拷贝（体积大）
Copy-Item "D:\__soft\MAA\resource\template\*Start*" ak\code\vision\templates\maa\ -Recurse
```

### 流水线（业务逻辑，JSON）
```json
{
  "name": "demo", "start": "main_menu",
  "nodes": [
    { "id": "main_menu", "roi": [0.60, 0.70, 0.95, 0.95], "interval_ms": 100,
      "recognize": { "type": "template", "name": "main/start", "threshold": 0.85 },
      "on_found": [ { "kind": "click", "params": { "target": "main_menu" } } ],
      "next": "in_battle", "timeout_ms": 120000, "on_timeout_goto": "main_menu" },
    { "id": "in_battle", "interval_ms": 50,
      "recognize": { "type": "color", "rgb": [220, 40, 40], "tol": 25, "point": { "rel_x": 0.5, "rel_y": 0.05 } },
      "on_found": [ { "kind": "key", "params": { "key": "space" } } ], "loop": true }
  ]
}
```

## 五、两个场景

### 场景① 识别并操控本地客户端（纯 GUI，不读内存）
`apps\run_client.py`：锁定窗口（标题/PID）→ 只抓窗口客户区 → 流水线识别 → SendInput/DirectInput 操作。
安全默认：`--dry-run` 只识别不动鼠标；`pydirectinput.FAILSAFE` 开启（鼠标甩到屏幕角落即急停）。

### 场景② 从攻略视频提取操作步骤
`apps\analyze_video.py`：把视频文件当帧源（同一内核，仅换采集插件）→ 逐帧识别 → 输出
`时间线 JSON`（帧号/时间/命中标签/分数/位置/对应动作），可直接转成"操作步骤表"。

> 与 MAA 的 `copilot`（作业文件）结合：视频时间线 → 作业步骤，是后续可做的增值方向。

## 六、与其它工具的分工

| 工具 | 定位 | 何时用 |
|---|---|---|
| **本内核** | 60 FPS 模板匹配 + 精确坐标输入 | 高频实时识别、批量视频分析、需要完全自定义 |
| `dsh-computer-use-win` 插件 | UIA 语义树 + 三层截图 + 三路输入 | 低频、语义化操作（点按钮、填表、读控件） |
| MAA | 成品日常自动化 + 2149 模板 + copilot | 直接跑日常任务，不必自己写 |
