# -*- coding: utf-8 -*-
"""append_r15.py — 记录：卡片检测改进、窗口按标题查找、DPI-aware。"""
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

## 十一、三项修正与当前状态（2026-09-15 续）

### 11.1 ✅ 卡片检测改进（根因之一）
旧 `find_cards()` 只用"列标准差"分段 ⇒ **把相邻卡片合并**，实测只返回 **2 段**
（(709,1002)、(1709,1002)）—— **而 (709,…) 正落在第 5~6 张卡片之间的间隙**，
所以"点选"根本没点到卡片上。

**改进版**（列梯度能量 `Sobel_x` + 列亮度均值 双通道，取分段较多者）：
实测 12 张卡片 ⇒ 返回 **10 段**，中心 **`[100, 275, 458, 627, 801, 980, 1136, 1352, 1644, 1858]`**，
可视化（`apps/card_probe.py` 画出红框+中线）**与画面吻合**。
⇒ **点选随即生效**（弹出干员详情 + 绿色可部署格稳定出现）。

### 11.2 ✅ 窗口查找的关键修正（根因之二）
PRTS+ 的 `src/mumu/mumu_connection.py` 全文要点：
```python
PARENT_HANDLE = win32gui.FindWindow(None, "MuMu模拟器12")               # 主窗口（按标题）
HANDLE = win32gui.FindWindowEx(PARENT_HANDLE, 0, None, "MuMuPlayer")    # ★ 子窗口：**按标题**找
# 其日志：Found the game window with handle 7801904, parent handle 983350
```
**两个要点**：
1. **`MuMuPlayer` 是"窗口标题"**（class 参数传 `None`）—— 本方此前按 class 找，自然失败；
2. **它拿到的 `HANDLE` = 7801904**，正是本方此前独立发现的 **`render_wnd`**
   ⇒ **目标窗口就是 render_wnd**。

### 11.3 ✅ DPI 感知（根因之三，PRTS+ 也做了）
```python
ctypes.windll.shcore.SetProcessDpiAwareness(2)     # PROCESS_PER_MONITOR_DPI_AWARE
```
**为什么关键**：若进程**不是** DPI-aware，`GetWindowRect` 返回的是**被 DPI 缩放后**的坐标
⇒ "帧坐标 → 窗口像素"的换算会整体偏移。本机屏幕 2560×1600 而窗口 1306×796，**存在缩放**
⇒ 本方已在 `WinInput.__init__` 中加入该调用。

### 11.4 当前状态
| 环节 | 状态 |
|---|---|
| 卡片检测 | ✅ 10 段，中心正确 |
| 目标窗口 | ✅ 按标题 `MuMuPlayer` 找到（3212124，与 PRTS+ 的 HANDLE 同类） |
| DPI 感知 | ✅ 已设置 |
| 暂停（点按钮） | ✅ |
| **F 键保持暂停** | ⚠️ **时好时坏**：上一轮 `key_down('f')` 稳定保持；本轮"先 `key_up` 再 `key_down`"后**未保持**（cost 46→47）⇒ 需排查"快速 up/down 配对"的时序 |
| **点选干员** | ✅ 稳定生效（详情 + 绿格） |
| **拖拽提交部署** | ❌ **仍未成功**（cost 不变、卡片不减） |

### 11.5 下一步
1. **暂停用"点按钮"而非 F**：F 的 up/down 语义容易出错；`ensure_paused()`（点暂停按钮 + 两次读数确认）
   已被证明可靠 ⇒ **部署全程用 `ensure_paused` 保证暂停，不依赖 F**；
2. **在"确认暂停"之后**再执行 PRTS+ 拖拽序列（mousedown → 一次 mousemove → 暂停保持 → mousemove → mouseup），
   去掉序列中的 `key_up/key_down('f')`；
3. 若仍失败，做**对照实验**：同一序列改用**真实鼠标**（`SetCursorPos`+`SendInput`）执行，
   以判定"本机是否必须使用真实输入"；
4. 另可尝试 `SendMessage` 的**超时变体** `SendMessageTimeout`，或改用 `PostMessage` 到该窗口配合更长间隔。
'''

s = io.open(DOC, encoding='utf-8').read()
if '十一、三项修正与当前状态' not in s:
    io.open(DOC, 'a', encoding='utf-8').write(EXTRA)
    print('已更新源码剖析文档')

ADD = (' **三项修正：卡片检测 / 窗口查找 / DPI 感知（2026-09-15）**：'
       '①**✅卡片检测改进（根因之一）**：旧 `find_cards()` 只用"列标准差"分段 ⇒ **把相邻卡片合并**，'
       '实测只返回 2 段（(709,1002)、(1709,1002)），**而 (709,…) 正落在第 5~6 张卡片之间的间隙** ⇒ '
       '"点选"根本没点到卡片；**改进版**（列梯度能量 + 列亮度双通道）实测返回 **10 段**，'
       '中心 **[100,275,458,627,801,980,1136,1352,1644,1858]**，可视化与画面吻合 ⇒ **点选随即生效**'
       '（详情 + 绿格稳定出现）；'
       '②**✅窗口查找修正（根因之二）**：读 PRTS+ `src/mumu/mumu_connection.py` 得知：'
       '`PARENT=FindWindow(None,"MuMu模拟器12")`、**`HANDLE=FindWindowEx(PARENT,0,None,"MuMuPlayer")`** ⇒ '
       '**`MuMuPlayer` 是"窗口标题"（class 传 None）**，本方此前按 class 找自然失败；'
       '且它拿到的 **HANDLE=7801904 正是本方独立发现的 `render_wnd`** ⇒ **目标窗口就是 render_wnd**；'
       '③**✅DPI 感知（根因之三）**：PRTS+ 调用 **`SetProcessDpiAwareness(2)`**；'
       '若进程非 DPI-aware，`GetWindowRect` 返回**缩放后坐标** ⇒ 换算整体偏移'
       '（本机屏幕 2560×1600、窗口 1306×796，确有缩放）⇒ 本方已加入；'
       '④**当前状态**：卡片检测 ✅、目标窗口 ✅、DPI ✅、暂停（点按钮）✅、点选干员 ✅（详情+绿格）；'
       '**F 键保持暂停时好时坏**（上轮稳定、本轮"先 up 再 down"后未保持，cost 46→47）；'
       '**拖拽提交部署仍失败**（cost 不变、卡片不减）；'
       '⑤**下一步**：**部署全程改用 `ensure_paused()`（点按钮 + 两次读数确认）保证暂停、不依赖 F**，'
       '在此前提下执行 PRTS+ 拖拽序列；若仍失败则做**真实鼠标对照实验**判定"是否必须真实输入"；'
       '另可试 `SendMessageTimeout` 或 `PostMessage` + 更长间隔；'
       '⑥**新增 `apps/card_probe.py`**（卡片检测细化 + 可视化）；'
       '⑦**合规**：仅窗口消息层注入（不移动真实光标）；未触碰游戏文件/内存。 | 2026-09-15 |')

r = io.open(REG, encoding='utf-8').read()
ra = '\n\n## 冲突记录'
r = r.replace(ra, ADD + ra, 1)
io.open(REG, 'w', encoding='utf-8', newline='').write(r)
print('台账已记录')

for src, sub in ((DOC, r'knowledge\04_数据对应与核验'),
                 (r'C:\Users\23922\Documents\ds_harness\ak\code\vision\plugins\action\win_input.py',
                  r'code\vision\plugins\action'),
                 (r'C:\Users\23922\Documents\ds_harness\ak\code\vision\plugins\action\deploy.py',
                  r'code\vision\plugins\action'),
                 (r'C:\Users\23922\Documents\ds_harness\ak\code\vision\apps\card_probe.py',
                  r'code\vision\apps')):
    d = os.path.join(DST, sub, os.path.basename(src))
    os.makedirs(os.path.dirname(d), exist_ok=True)
    shutil.copy2(src, d)
shutil.copy2(REG, os.path.join(DST, 'management', 'tasks_registry.md'))
print('同步完成')
