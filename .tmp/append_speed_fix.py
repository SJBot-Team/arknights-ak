# -*- coding: utf-8 -*-
"""append_speed_fix.py — 修正：子弹时间是最高精度过帧场景（用户补充）。"""
import io
import os
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')

DOC = r'C:\Users\23922\Documents\ds_harness\ak\knowledge\04_数据对应与核验\52_过帧与流速标定.md'
REG = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
DST = r'E:\__file\ak_kb\kb'

EXTRA = '''

---

## 五、★重要修正（用户 2026-09-15 补充）

> 「过帧宏为图形界面层的实现，**偶尔失效是正常的**，三种流速下的过帧均重要，
> **高精度需求的场景一般仅用子弹时间过帧**。」

### 5.1 对上文结论的修正
前文第 1 节曾写"子弹时间下过帧基本失效"，**这个表述不准确，予以修正**：

| 原表述 | 修正后 |
|---|---|
| "子弹时间下过帧失效" | **子弹时间是"粒度最细、精度最高"的过帧场景**；单次宏推进 0~1 帧是**正常现象**（游戏最慢），要推进整帧需**多发几次或换更长宏** |
| "过帧宏应避免在子弹时间使用" | **恰恰相反：高精度定轴应当"仅用子弹时间过帧"** |

### 5.2 为什么子弹时间精度最高
子弹时间（点选干员后）游戏内时间流速被显著降低 ⇒
**同样的真实时间内推进的游戏帧数最少** ⇒ **每帧对应更长的真实时间** ⇒
**过帧宏的"时间分辨率"换算到帧时最细** ⇒ 最容易把操作**精确停在某一帧**。

### 5.3 过帧宏的性质（据用户说明）
- 云迹方案的 R/T/Y（前进 12/33/166ms）是**图形界面层（模拟器宏）**的实现；
- 它依赖模拟器的按键映射与游戏的 UI 响应 ⇒ **偶尔失效是正常的**（不是实现有误）；
- ⇒ **使用时应"闭环校验"**：每发一次过帧后**读费用条相位**确认是否真的前进，
  未前进就**补发**，而不是一次性假定推进了 N 帧。

### 5.4 修正后的过帧策略
```
① 高精度定轴（首选）：子弹时间（点选干员）→ 用 T/R/Y 反复微调，
   每次读相位校验（6px = 1 帧），未前进则补发；必要时用更长宏（Y=166ms）
② 中等精度：1 倍速 → T(33ms) ≈ 1 帧
③ 快速粗调：2 倍速 → T(33ms) ≈ 2 帧（用于大跨度逼近）
④ 三种流速都要支持：先 read_speed() 识别，再按流速选择宏与次数
```

## 六、附：PRTS+ 的后台鼠标实现（本轮从开源仓库取得，★解决"不抢鼠标"）

来源：<https://github.com/jue-ce-zhe/prts-plus> → `src/mumu/mumu_controller.py`

```python
import win32api, win32con, win32gui

def mouseclick(pos):                                   # pos 为像素坐标
    win32api.SendMessage(HANDLE, win32con.WM_LBUTTONDOWN, 0, win32api.MAKELONG(*pos))
    win32api.SendMessage(HANDLE, win32con.WM_LBUTTONUP,   0, win32api.MAKELONG(*pos))

def mousedown(pos):
    win32api.SendMessage(HANDLE, win32con.WM_LBUTTONDOWN, 0, win32api.MAKELONG(*pos))

def mouseup(pos):
    win32api.SendMessage(HANDLE, win32con.WM_LBUTTONUP, win32con.MK_LBUTTON, win32api.MAKELONG(*pos))

def mousemove(pos):
    win32api.SendMessage(HANDLE, win32con.WM_MOUSEMOVE, win32con.MK_LBUTTON, win32api.MAKELONG(*pos))

def pause():   # 暂停用"鼠标侧键2"
    win32api.SendMessage(HANDLE, config.WM_XBUTTONDOWN, config.XBUTTON2, config.DEFAULT_COORDINATES)
    win32api.SendMessage(HANDLE, config.WM_XBUTTONUP,   config.XBUTTON2, config.DEFAULT_COORDINATES)

def esc():     # ESC/返回用"鼠标侧键1"
    win32api.SendMessage(HANDLE, config.WM_XBUTTONDOWN, config.XBUTTON1, config.DEFAULT_COORDINATES)
    win32api.SendMessage(HANDLE, config.WM_XBUTTONUP,   config.XBUTTON1, config.DEFAULT_COORDINATES)

# 坐标装饰器：**比例坐标(0~1) → 像素**，基于 **GetWindowRect 的完整窗口尺寸**
def handle_coordinates(func):
    window_rect = win32gui.GetWindowRect(HANDLE)
    w, h = window_rect[2]-window_rect[0], window_rect[3]-window_rect[1]
    return func((int(x*w), int(y*h)))
```

### 三条关键结论（解释了本方的失败）
1. **必须用 `SendMessage`（同步）而非 `PostMessage`（异步）** —— 后者会被模拟器忽略；
2. **坐标基准是 `GetWindowRect`（完整窗口）而非客户区**，且用**比例**换算；
3. **`WM_MOUSEMOVE` 要带 `MK_LBUTTON`**，模拟器才识别为"拖动中"；
   ⇒ **全程不移动真实光标 ⇒ 不抢用户的鼠标**（正是用户要求的效果）。
4. 另外：PRTS+ 把**"暂停"绑到鼠标侧键2、"ESC/返回"绑到侧键1**
   （用 `WM_XBUTTONDOWN/UP` + `XBUTTONn` 投递）—— 可作为"不依赖键盘焦点"的暂停/返回手段。

**本方已在 `plugins/action/win_input.py` 实现**：
`sm_mouse(kind, x, y)`、**`sm_drag(points)`**（PRTS+ 式划火柴）、**`sm_xbutton(which)`**。
'''

s = io.open(DOC, encoding='utf-8').read()
if '五、★重要修正' not in s:
    io.open(DOC, 'a', encoding='utf-8').write(EXTRA)
    print('已更新标定文档')

ADD = (' **过帧结论修正 + PRTS+ 后台鼠标实现取得（2026-09-15）**：'
       '①**用户补充**："过帧宏为图形界面层的实现，**偶尔失效是正常的**，三种流速下的过帧均重要，'
       '**高精度需求的场景一般仅用子弹时间过帧**" ⇒ **修正上一轮"子弹时间下过帧失效"的表述**：'
       '子弹时间是**粒度最细、精度最高**的过帧场景，单次宏推进 0~1 帧属正常（游戏最慢），'
       '要推进整帧需**多发几次或换更长宏**；**高精度定轴应当"仅用子弹时间过帧"**；'
       '②**过帧策略修正**：高精度 → 子弹时间 + T/R/Y 反复微调（**每次读相位闭环校验，未前进就补发**）；'
       '中等 → 1 倍速 T≈1 帧；快速粗调 → 2 倍速 T≈2 帧（大跨度逼近）；三种流速都要支持；'
       '③**★从 PRTS+ 开源仓库取得后台鼠标实现**（`github.com/jue-ce-zhe/prts-plus` → '
       '`src/mumu/mumu_controller.py`，该仓库还含 `hook/`、`src/logic/`、`src/utils/`、'
       '`sample 1-7.xlsm` 示例轴表）：**用 `SendMessage`（同步，非 PostMessage）** 投递 '
       '`WM_LBUTTONDOWN/UP`、`WM_MOUSEMOVE`（**带 `MK_LBUTTON`**）；**坐标用 `GetWindowRect` '
       '完整窗口尺寸的"比例"换算**；**暂停绑鼠标侧键2、ESC/返回绑侧键1**（`WM_XBUTTONDOWN/UP` + `XBUTTONn`）；'
       '⇒ **这三条解释了本方此前鼠标注入失败的原因**，且**不移动真实光标 ⇒ 不抢用户鼠标**，'
       '正是用户要求的效果；'
       '④**本方已实现**（`plugins/action/win_input.py`）：`sm_mouse(kind,x,y)`、**`sm_drag(points)`**'
       '（PRTS+ 式划火柴）、**`sm_xbutton(which)`**（侧键暂停/返回）；'
       '⑤**产出更新**：`knowledge/04/52_过帧与流速标定.md` 新增 §五（结论修正）、§六（PRTS+ 实现全文摘录与三条结论）；'
       '⑥**下一步**：用 `sm_drag` 实测划火柴（左键按下→带 MK_LBUTTON 连续移动→抬起），'
       '并实现 `advance_frames(n, speed)` 闭环过帧；'
       '⑦**合规**：仅窗口消息层注入（不移动真实光标）+ 模拟器官方键鼠方案；未触碰游戏文件/内存。 | 2026-09-15 |')

r = io.open(REG, encoding='utf-8').read()
ra = '\n\n## 冲突记录'
r = r.replace(ra, ADD + ra, 1)
io.open(REG, 'w', encoding='utf-8', newline='').write(r)
print('台账已记录')

for src, sub in ((DOC, r'knowledge\04_数据对应与核验'),
                 (r'C:\Users\23922\Documents\ds_harness\ak\code\vision\plugins\action\win_input.py',
                  r'code\vision\plugins\action')):
    d = os.path.join(DST, sub, os.path.basename(src))
    os.makedirs(os.path.dirname(d), exist_ok=True)
    shutil.copy2(src, d)
shutil.copy2(REG, os.path.join(DST, 'management', 'tasks_registry.md'))
print('同步完成')
