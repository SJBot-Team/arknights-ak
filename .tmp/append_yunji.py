# -*- coding: utf-8 -*-
"""append_yunji.py — 云迹方案宏定义（划火柴/过帧/时停）提取 + 实测结论。"""
import io
import os
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')

DOC = r'C:\Users\23922\Documents\ds_harness\ak\knowledge\04_数据对应与核验\51_划火柴_暂停态精确部署_实现资料.md'
REG = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
DST = r'E:\__file\ak_kb\kb'

EXTRA = '''

---

## 六、★云迹方案（用户指定：过帧/划火柴/0帧暂停功能较完善）宏定义全录

来源：`%APPDATA%\\Netease\\MuMuPlayer\\data\\keymapConfig\\com.hypergryph.arknights-【16比9 60帧 V3.6】by 云迹60帧.json`（20 个键位）

### 6.1 过帧（★"精确到帧"的核心）
| 宏 | 键 | 动作 |
|---|---|---|
| **前进 12ms** | R | `release_all → keyboard_press:11 → sleep:10 → release:11 → sleep:12 → click_rel:(0.916610,0.069880)` |
| **前进 33ms** | T | 同上，`sleep:22` |
| **前进 166ms** | Y | 同上，`sleep:155` |

**⇒ 规律 = "让游戏运行 N ms，然后点一次暂停按钮"**。
暂停按钮相对坐标 ≈(0.9166, 0.0699) ⇒ 帧 ≈**(1760, 75)**。
（60 帧下 12/33/166ms ≈ 0.7/2/10 帧；三档组合可拼出任意帧数 ⇒ **这就是"过帧"**）

### 6.2 0帧划火柴（暂停时按住拖动）★核心
触发：**鼠标右键**（60帧版）或 **鼠标中键 forward_mouse**（144帧版）
```
release_all
mouse_release:1
keyboard_press:11, keyboard_release:11, keyboard_release:11
curve_first_point_sleep_time:17          ← 曲线首点延时（144帧版为 7）
curve_last_point_sleep_time:until_release_cmd   ← 末点"等玩家松开"
curve_rel:mouse;(3.405995, 6.053269)     ← ★ 拖动曲线（相对量）
mouse_press:1                            ← ★ 按住左键
keyboard_press:158, keyboard_release:158, keyboard_release:158   ← ★ 时停
release: release_all, mouse_release:1
```
**⇒ 划火柴 = "按住右键 → 拖动（曲线）→ 松开"**，全程在暂停态进行。

### 6.3 时停（F 键）
`press: keyboard_press:158` / `release: keyboard_release:158`
（另有"开局暂停" C 键：`start_loop:until_release → keyboard_press:158 → release:158 → sleep:5 → stop_loop`）

### 6.4 其它
- **0帧技能（暂停时）**：鼠标中键；`... mouse_press:1 → click_rel:(0.915932,0.068675) → mouse_release:1 → sleep:155 → keyboard_press:27 → sleep:33 → release:27`（27 = ESC）
- **0帧撤退（暂停时）**：鼠标后退键；`... keyboard_press:26 → sleep:33 → release:26`
- **暂停选中（W 键）**：`... click_rel:(0.916894,0.070218)`
- **一键撤退（Q）**、**一键技能（E）**、**手动撤退（A）**、**手动技能（S）**、**子弹时间（Z）**、**视角切换（Tab）**

## 七、本方实测（2026-09-15）

| 试验 | 结果 |
|---|---|
| `adb shell input keyevent 111(ESC)` | ❌ 不触发宏（宏在模拟器软件层） |
| MCP `SendKeys` 发 `f`（窗口已激活） | ❌ 未暂停 |
| **自写 `WinInput`（SendInput，含扫描码）发 `f`**（窗口已聚焦成功） | ❌ **仍未暂停** |

**⇒ 结论：注入链路本身是通的（窗口聚焦成功、SendInput 无错），但游戏侧没有产生"时停"**，
最可能的原因是 **MuMu 当前未启用含这些宏的键鼠方案**（或按键映射未开启）。

## 八、需要用户协助确认（关键）
1. **MuMu 的"键鼠方案"当前启用的是哪一个？** 是否已切换到 **云迹方案**
   （`【16比9 60帧 V3.6】by 云迹60帧` 或 144 帧版）？
2. **按键映射是否处于开启状态**（游戏内右上角键鼠图标高亮）？
3. 若尚未启用，请切到云迹方案；启用后我即可用 `WinInput` 复现
   **"F 时停 → 右键划火柴拖拽 → R/T/Y 过帧"** 的完整精确帧流程。

## 九、本方已就绪的组件（待方案启用即可用）
- `plugins/action/win_input.py`：**Windows 层 SendInput 注入**（鼠标绝对/相对移动、左/右键按下松开、
  曲线拖拽 `drag_frame(points, curve_steps=...)`、按键 `key_tap/key_hold`、窗口聚焦 `focus_window`）；
- `plugins/action/deploy.py`：`ensure_paused / find_cards / find_green_cells / find_diamond / set_direction / frame_of`；
- 注入前必须保证 **MuMu 窗口在前台**（否则模拟器停止渲染）。
'''

s = io.open(DOC, encoding='utf-8').read()
if '六、★云迹方案' not in s:
    io.open(DOC, 'a', encoding='utf-8').write(EXTRA)
    print('已更新划火柴资料文档')
else:
    print('已有该节')

ADD = (' **★★云迹方案宏定义全录 + 划火柴实现路线确认（2026-09-15，用户指引"用云迹方案，AFA 为 pc 端权威方案"）**：'
       '①**从本机方案 JSON 提取到云迹方案（60帧 V3.6，20 个键位）的完整宏定义**：'
       '**(a) ★过帧**：前进 12ms(R) / 33ms(T) / 166ms(Y) —— 规律为「`keyboard_press:11 → sleep:10 → release:11 → '
       'sleep:N → click_rel:(0.916610,0.069880)`」，即**让游戏运行 N ms 后点一次暂停按钮**；'
       '暂停按钮相对坐标 ≈(0.9166,0.0699) ⇒ 帧 ≈**(1760,75)**；三档组合可拼出任意帧数；'
       '**(b) ★0帧划火柴（暂停时按住拖动）**：鼠标右键触发（144帧版为鼠标中键），动作序列 '
       '`release_all → mouse_release:1 → keyboard_press:11 → curve_first_point_sleep_time:17 → '
       'curve_last_point_sleep_time:until_release_cmd → curve_rel:mouse;(3.405995,6.053269) → mouse_press:1 → '
       'keyboard_press:158`，release 为 `release_all, mouse_release:1` ⇒ **划火柴 = 按住右键 → 曲线拖动 → 松开**；'
       '**(c) 时停（F）**：`keyboard_press:158`；**(d) 0帧技能（鼠标中键）**、**(e) 0帧撤退（鼠标后退键）**、'
       '**(f) 暂停选中（W）**、一键撤退(Q)/技能(E)、子弹时间(Z)、视角切换(Tab) 等；'
       '②**本方实测（注入链路已通但游戏侧无反应）**：`adb keyevent ESC` ❌；MCP `SendKeys` 发 f ❌；'
       '**自写 `WinInput`（SendInput，含扫描码）发 f，窗口聚焦成功、无报错，游戏仍未暂停** ❌ '
       '⇒ **最可能的原因：MuMu 当前未启用含这些宏的键鼠方案（或按键映射未开启）**；'
       '③**新增 `plugins/action/win_input.py`（Windows 层 SendInput 注入）**：鼠标绝对/相对移动、左右键按下松开、'
       '**曲线拖拽 `drag_frame(points, curve_steps=…)`**、按键 `key_tap/key_hold`、窗口聚焦 `focus_window`；'
       '④**⚠ 需用户协助确认**：(a) MuMu 当前启用的是哪个键鼠方案，是否已切到**云迹方案**'
       '（`【16比9 60帧 V3.6】by 云迹60帧` / 144 帧版）；(b) **按键映射是否已开启**（游戏内右上角键鼠图标）；'
       '启用后我即可复现"**F 时停 → 右键划火柴拖拽 → R/T/Y 过帧**"的完整精确帧流程；'
       '⑤合规：仅图形界面级操控（模拟器官方键鼠方案 + Windows 层注入）；未触碰游戏文件/内存。 | 2026-09-15 |')

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
