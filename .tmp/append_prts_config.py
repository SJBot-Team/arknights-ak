# -*- coding: utf-8 -*-
"""append_prts_config.py — 补全：PRTS+ 常量配置 + 坐标映射算法。"""
import io
import os
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')

DOC = r'C:\Users\23922\Documents\ds_harness\ak\knowledge\04_数据对应与核验\53_PRTS+部署实现_源码剖析.md'
REG = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
DST = r'E:\__file\ak_kb\kb'

EXTRA = '''

---

## 五、常量配置（`src/config.py` 全文摘录）★关键参数

```python
class MuMuEmulatorConfig:
    DEFAULT_COORDINATES = 0x00640064      # (100,100) 默认坐标
    WINDOW_NAME     = "MuMu模拟器12"       # 主窗口
    SUB_WINDOW_NAME = "MuMuPlayer"        # ★ 子窗口（本方此前误用 UIA 的 class 名 nemuwin）
    WM_XBUTTONDOWN, WM_XBUTTONUP = 0x020B, 0x020C
    XBUTTON1, XBUTTON2 = 0x00010000, 0x00020000

class GameRatioConfig:                    # 全部为**比例坐标(0~1)**
    COST_AREA_RATIO        = (0.906, 0.685, 1, 0.755)   # 费用条区域
    COST_NUMBER_AREA_RATIO = (0.33, 0, 1, 0.9)
    OPERATOR_AREA_RATIO    = (0, 0.8, 1, 1)             # 待部署区
    LAST_OPER_RATIO        = (0.95, 0.9)                # 上一次操作的干员（用于进子弹时间）
    RETREAT_RATIO          = (0.4569, 0.3352)
    SKILL_RATIO            = (0.6412, 0.5857)
    START_BUTTON_RATIO     = (0.87, 0.74)
    SPEED_BUTTON_RATIO     = (0.86, 0.07)               # 倍速按钮
    PAUSE_BUTTON_RATIO     = (0.94, 0.07)               # 暂停按钮
    DIRECTION_RATIO        = 0.2                        # 定朝向拖动距离
    DEPLOY_DRAG_RATIO      = 0.03                       # 部署拖拽距离（头像向上拖）
    DEPLOY_DELTA_RATIO     = 0.02                       # 部署落点偏移
    OPERATOR_SELECTED_RATIO= 0.9                        # 判断"已选中"的 y 阈值

class ImageProcessingConfig:
    WHITE_THRESHOLD = 160
    SCREEN_STANDARD_SIZE = (1280, 720)
    AVATAR_STANDARD_SIZE = (120, 120);  AVATAR_CROP_SIZE = (60, 60)
    OCR_CONFIDENCE_THRESHOLD = 60;  TEMPLATE_MATCH_THRESHOLD = 0.8

class ViewCalculationConfig:              # 坐标映射用
    FROM_RATIO = 9/16;  TO_RATIO = 3/4;  NEAR = 0.3;  FAR = 1000

class GameTimeConfig:
    TICK_MAX_DEFAULT = 30                 # ★ 1 秒 = 30 tick（与费用尺口径一致）

class PerformActionConfig:                # ★★ 核心时序参数
    BULLET_THRESHOLD = 15                 # 进入"子弹时间"的提前量（帧）
    FRAME_THRESHOLD  = 2                  # 帧精度阈值（帧）
    MINIMUM_WAITTIME = 0.02
    FRAME_WAITTIME   = 0.1                # ★ 逐帧推进的等待：恢复 → 等 100ms → 暂停
    GENERAL_WAITTIME = 0.3
```

**与己方观测的互证**：
- `PAUSE_BUTTON_RATIO=(0.94,0.07)` ⇒ 帧 (1805,76)，与本方实测的 (1806,80)、MAA 换算的 (1807,79) **三者一致**；
- `BULLET_THRESHOLD=15` / `FRAME_THRESHOLD=2` 与它运行日志中的
  `Set bullet threshold to 15.0` / `Set frame threshold to 2.0` **完全一致**；
- `TICK_MAX_DEFAULT=30`（1 秒 30 tick）与本方"费用条满一次 = 30 帧"的结论**一致**。

---

## 六、坐标映射算法（`src/logic/calc_view.py`）★补全"格子→屏幕坐标"

PRTS+ 用**3D 透视投影**把地图格子映射为**屏幕比例坐标**：

```python
DEGREE = math.pi / 180
height, width = level["height"], level["width"]
x, y, z = level["view"][1 if side else 0]        # ★ 视角参数取自关卡数据

transform_matrix = [[1,0,0,-x],[0,1,0,-y],[0,0,1,-z],[0,0,0,1]]      # 平移
perspective_matrix = [[FROM_RATIO/tan(20°),0,0,0],                   # 20° 视角
                      [0,1/tan(20°),0,0],
                      [0,0,-(FAR+NEAR)/(FAR-NEAR), -(FAR*NEAR*2)/(FAR-NEAR)],
                      [0,0,-1,0]]
rotate_x_matrix = 绕 X 轴 30°（俯视角）
rotate_y_matrix = 绕 Y 轴 10°（仅 side 视图）

final = perspective @ rotate_x @ ([rotate_y] if side else I) @ transform

for i in range(height):
  for j in range(width):
    tile = level["tiles"][i][j]
    map_point = [j-(width-1)/2, (height-1)/2-i, tile["heightType"]*-0.4, 1]   # 格子中心（含高度偏移）
    vp = final @ map_point
    vp = vp / vp[3]                  # 透视除法
    vp = (vp + 1) / 2                # NDC → [0,1]
    out[i][j] = (vp[0], 1 - vp[1])   # ★ y 反转，得到屏幕比例坐标
```

**要点**：
1. **正视(front)与侧视(side)两套矩阵**：部署用 `view_pos_side`、技能/撤退用 `view_pos_front`；
2. **格子高度参与投影**：`heightType * -0.4`（高台格在屏幕上更靠上）；
3. **视角参数 `level["view"]` 来自关卡数据** ⇒ 本方也能取到（`mapData` 同级字段）；
4. 输出即 **`mouseclick(pos)` 需要的比例坐标** ⇒ 与本方的"帧坐标 / 1920×1080"可直接换算
   （比例 = 帧坐标 / 分辨率）。

---

## 七、本方待对齐清单（按 PRTS+ 修正）

| # | 项 | 本方当前 | 应改为（PRTS+） |
|---|---|---|---|
| 1 | 鼠标注入 | `PostMessage` ✗ | **`SendMessage`（同步）** |
| 2 | 移动事件 | `WM_MOUSEMOVE` 无 `MK_LBUTTON` | **带 `MK_LBUTTON`** |
| 3 | 坐标基准 | 客户区 + 标题栏校正 | **`GetWindowRect` 完整窗口 × 比例** |
| 4 | 子窗口 | `nemuwin`（UIA class） | **`MuMuPlayer`** |
| 5 | 暂停/恢复 | 点暂停按钮 | **鼠标侧键2（切换）**；**侧键1 = 暂停** |
| 6 | 部署拖拽 | 多次 mousemove | **一次 mousemove + 中途 `esc()` 暂停 + 再 mousemove + mouseup** |
| 7 | 坐标映射 | 手工估格子坐标 | **用 `calc_view` 式 3D 投影（front/side 两套）** |
| 8 | 逐帧推进 | 无 | **`while time<target: 恢复 → sleep(0.1) → 暂停`**（子弹时间下 1 次 ≈ 1 帧） |
| 9 | 阈值 | 无 | **BULLET_THRESHOLD=15、FRAME_THRESHOLD=2** |
'''

s = io.open(DOC, encoding='utf-8').read()
if '五、常量配置' not in s:
    io.open(DOC, 'a', encoding='utf-8').write(EXTRA)
    print('已更新源码剖析文档')

ADD = (' **★★★★★★补全 PRTS+ 常量配置与坐标映射算法（2026-09-15）**：'
       '①**取得 `src/config.py` 全文参数**：'
       '**(a) 输入层**：`WINDOW_NAME="MuMu模拟器12"`、**`SUB_WINDOW_NAME="MuMuPlayer"`**'
       '（本方此前误用 UIA 的 class 名 `nemuwin`）、侧键常量 `XBUTTON1/2 = 0x00010000/0x00020000`；'
       '**(b) 比例坐标**：`PAUSE_BUTTON_RATIO=(0.94,0.07)`、`SPEED_BUTTON_RATIO=(0.86,0.07)`、'
       '`LAST_OPER_RATIO=(0.95,0.9)`、`RETREAT_RATIO`、`SKILL_RATIO`、`START_BUTTON_RATIO`、'
       '`DIRECTION_RATIO=0.2`、**`DEPLOY_DRAG_RATIO=0.03`**、`DEPLOY_DELTA_RATIO=0.02`、'
       '`OPERATOR_SELECTED_RATIO=0.9`；'
       '**(c) ★核心时序**：**`BULLET_THRESHOLD=15`、`FRAME_THRESHOLD=2`**'
       '（**与它运行日志的 15.0/2.0 完全一致**）、**`FRAME_WAITTIME=0.1`**（逐帧推进的等待）、'
       '`MINIMUM_WAITTIME=0.02`、`GENERAL_WAITTIME=0.3`；'
       '**(d) `TICK_MAX_DEFAULT=30`** ⇒ **1 秒 = 30 tick，与本方"费用条满一次=30帧"一致**；'
       '**(e) `PAUSE_BUTTON_RATIO` 换算帧 (1805,76)**，与本方实测 (1806,80)、MAA 换算 (1807,79) **三者一致**；'
       '②**取得 `src/logic/calc_view.py` 的坐标映射算法**：用 **3D 透视投影**（20° 视角、绕 X 轴 30°、'
       'side 视图再绕 Y 轴 10°）把地图格子映射为**屏幕比例坐标**，**格子高度 `heightType*-0.4` 参与投影**，'
       '**视角参数取自关卡数据 `level["view"]`**，输出 **front/side 两套**'
       '（部署用 side、技能/撤退用 front）；'
       '③**整理出「本方待对齐清单」9 条**：`PostMessage→SendMessage`、`WM_MOUSEMOVE` 加 `MK_LBUTTON`、'
       '坐标基准改 `GetWindowRect`×比例、子窗口改 `MuMuPlayer`、暂停/恢复改**鼠标侧键**、'
       '部署拖拽改**一次 mousemove + 中途 esc 暂停**、坐标映射改用 3D 投影、'
       '新增**逐帧推进循环**（恢复→sleep0.1→暂停）、采用 **BULLET/FRAME 双阈值**；'
       '④**产出更新**：`knowledge/04/53_PRTS+部署实现_源码剖析.md` 新增 §五（常量配置）、'
       '§六（坐标映射算法）、§七（待对齐清单）；'
       '⑤**下一步**：按清单 1–5 先改输入层与暂停控制（成本最低、收益最大），再用 3D 投影算格子坐标，'
       '最后按 PRTS+ 序列跑一次完整部署；'
       '⑥**合规**：仅窗口消息层注入（不移动真实光标、不抢用户鼠标）；未触碰游戏文件/内存。 | 2026-09-15 |')

r = io.open(REG, encoding='utf-8').read()
ra = '\n\n## 冲突记录'
r = r.replace(ra, ADD + ra, 1)
io.open(REG, 'w', encoding='utf-8', newline='').write(r)
print('台账已记录')
shutil.copy2(DOC, os.path.join(DST, 'knowledge', '04_数据对应与核验', os.path.basename(DOC)))
shutil.copy2(REG, os.path.join(DST, 'management', 'tasks_registry.md'))
print('同步完成')
