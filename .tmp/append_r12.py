# -*- coding: utf-8 -*-
"""append_r12.py — 记录：窗口定位、侧键依赖方案、部署序列要点。"""
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

## 八、窗口目标与侧键的实测修正（2026-09-15 续）

### 8.1 窗口层级（实测枚举）
```
主窗口   hwnd=4000354  class=ShellWindow  title="MuMu模拟器12"   GetWindowRect=1306×796
 └ Qt5156QWindowIcon   hwnd=3212124      （外层容器）
 └ nemuwin             hwnd=1247902      （渲染/接收输入）
```
- **`MuMuPlayer` 不是"窗口类名"，而是"窗口标题"** —— PRTS+ 的 `SUB_WINDOW_NAME` 是用
  `FindWindow(标题)` 取的（本方先前按 class 找，自然找不到）；
- **★实测：向 `nemuwin`（渲染子窗口）发 `SendMessage` 鼠标消息 ⇒ 生效**
  （成功弹出干员详情面板 + 地图出现绿色可部署高亮格）；
- **★实测：向"主窗口"发同样的消息 ⇒ 无效**（侧键、鼠标均无反应）
  ⇒ **目标窗口应为渲染子窗口 `nemuwin`**。

### 8.2 鼠标侧键依赖键鼠方案
- PRTS+ 用**鼠标侧键**做 `pause()`（侧键2）/`esc()`（侧键1），但那是它**自己的键鼠方案**
  （`PRTS+键鼠方案示例.json`）里绑定的；
- **本机当前启用的是"云迹方案"，其中并没有侧键绑定** ⇒
  **向窗口投递 `WM_XBUTTONDOWN/UP` 无任何效果**（已实测）；
- ⇒ **本方暂用"键盘宏"替代**：**F = 时停（切换）**、**R/T/Y = 过帧**（均已实测生效），
  这与云迹方案匹配；若将来切换到 PRTS+ 方案，则可改用侧键。

### 8.3 PRTS+ 部署序列的要点（再强调，便于本方实现）
```python
mouseclick(action.avatar_pos)          # ① 点选干员（avatar_pos 是"卡片头像"的比例坐标）
pause()                                # ② 恢复（切换）
mousedown(action.avatar_pos)           # ③ 在头像上按下
mousemove(middle_pos)                  # ④ 只移动一次：middle_pos = (x, y - DEPLOY_DRAG_RATIO)
esc()                                  # ⑤ 暂停
mousemove(view_pos_side + DELTA)       # ⑥ 移到目标格（3D 投影算出的 side 视图坐标）
mouseup(view_pos_side + DELTA)         # ⑦ 抬起 ⇒ 完成部署
# ⑧ 定朝向：mousedown(view_pos_side) → mousemove(dir_pos) → mouseup(dir_pos)
```
**关键差异点（本方此前缺失）**：
- **④ 只移动一次**（不是多次）；
- **⑤ 中途 `esc()` 暂停**（这是"划火柴"的核心节奏）；
- **⑥⑦ 的落点是 `view_pos_side`（3D 投影坐标）**，不是"看起来像格子的像素位置"。

### 8.4 下一步
1. `find_render_hwnd` 回退到 **`nemuwin`**（本方实测有效）；
2. **实现 3D 投影坐标映射**（`calc_view` 式，front/side 两套），用关卡数据的 `view` 参数；
3. 按 8.3 序列跑一次完整部署，并用"卡片消失 / 可放置数 −1 / 费用扣除"三重判据校验；
4. 逐帧推进用 **`F` 时停 + `T/R/Y` 过帧**（云迹方案），并在每步读相位闭环校验。
'''

s = io.open(DOC, encoding='utf-8').read()
if '八、窗口目标与侧键的实测修正' not in s:
    io.open(DOC, 'a', encoding='utf-8').write(EXTRA)
    print('已更新源码剖析文档')

ADD = (' **窗口目标/侧键的实测修正（2026-09-15）**：'
       '①**枚举出窗口层级**：主窗口（hwnd 4000354，class=ShellWindow，title="MuMu模拟器12"，GetWindowRect=1306×796）'
       '→ `Qt5156QWindowIcon`(3212124) → **`nemuwin`(1247902)**；'
       '**`MuMuPlayer` 不是类名而是窗口标题**（PRTS+ 的 `SUB_WINDOW_NAME` 用 FindWindow(标题) 取）；'
       '②**★实测结论**：**向 `nemuwin`（渲染子窗口）发 `SendMessage` 鼠标消息 ⇒ 生效**'
       '（成功弹出干员详情 + 地图出现绿色可部署高亮格）；'
       '**向主窗口发同样消息 ⇒ 无效** ⇒ **目标窗口应为渲染子窗口 `nemuwin`**（本方曾误改为主窗口，已纠正）；'
       '③**鼠标侧键依赖键鼠方案**：PRTS+ 的 pause/esc 用侧键，但那是它**自己的方案**里绑定的；'
       '**本机当前启用云迹方案、其中无侧键绑定** ⇒ **投递 `WM_XBUTTONDOWN/UP` 无任何效果**（已实测）'
       '⇒ **本方暂用键盘宏替代**（F 时停、R/T/Y 过帧，均已实测生效）；'
       '④**再次强调 PRTS+ 部署序列要点**（本方此前缺失的三点）：'
       '**④ 拖拽只移动一次**（`middle_pos = (x, y - DEPLOY_DRAG_RATIO)`）；'
       '**⑤ 中途要 `esc()` 暂停**（这是"划火柴"的核心节奏）；'
       '**⑥⑦ 落点是 `view_pos_side`（3D 投影算出的 side 视图坐标）**，不是"看起来像格子的像素位置"；'
       '⑤**下一步**：`find_render_hwnd` 回退到 `nemuwin`；**实现 3D 投影坐标映射**（calc_view 式、front/side 两套）；'
       '按 8.3 序列跑完整部署并用三重判据校验；逐帧推进用 F + T/R/Y 并每步读相位闭环；'
       '⑥**合规**：仅窗口消息层注入（不移动真实光标、不抢用户鼠标）；未触碰游戏文件/内存。 | 2026-09-15 |')

r = io.open(REG, encoding='utf-8').read()
ra = '\n\n## 冲突记录'
r = r.replace(ra, ADD + ra, 1)
io.open(REG, 'w', encoding='utf-8', newline='').write(r)
print('台账已记录')
shutil.copy2(DOC, os.path.join(DST, 'knowledge', '04_数据对应与核验', os.path.basename(DOC)))
shutil.copy2(REG, os.path.join(DST, 'management', 'tasks_registry.md'))
print('同步完成')
