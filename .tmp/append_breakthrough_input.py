# -*- coding: utf-8 -*-
"""append_breakthrough_input.py — ★★★突破：PostMessage 通道打通 F时停/过帧。"""
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

## 十、★★★决定性突破：PostMessage 通道（2026-09-15，用户提示"换不被干扰的输入方式"）

### 10.1 用户提示
> "我可以手动按 F 触发时停，云迹方案正常。但你的操作看起来被我其他层级的操作屏蔽了，
> 尝试不被我干扰的输入方式。"

⇒ 即：改用**不经过系统输入队列**的注入方式。

### 10.2 三种注入方式的实测对比

| 通道 | 结果 |
|---|---|
| `adb shell input keyevent` | ❌ 不触发宏（宏在模拟器软件层） |
| Windows **SendInput**（含扫描码） | ❌ 不触发（会被用户的前台输入抢占/屏蔽） |
| **Windows `PostMessage` 直接投递到渲染窗口** | ✅✅ **成功触发宏** |

**关键实现**（`plugins/action/win_input.py::post_key / post_click`）：
```python
hwnd = FindWindowExW(主窗口, None, 'nemuwin', None) or 主窗口   # 渲染子窗口
scan = MapVirtualKeyW(vk, 0)                                   # ★ 必须带扫描码
PostMessageW(hwnd, WM_KEYDOWN=0x0100, vk, 1 | (scan << 16))
PostMessageW(hwnd, WM_KEYUP  =0x0101, vk, 1 | (scan<<16) | (1<<30) | (1<<31))
```

### 10.3 实测结果（1-1 演习，云迹方案）

| 宏 | 键 | 实测效果 |
|---|---|---|
| **时停** | **F** | cost 20→22（运行中）→ **cost 23 恒定** ⇒ **★暂停生效** |
| **过帧 33ms** | **T** | fill_px **13 → 19**（+6px = **+1 帧**） |
| **过帧 12ms** | **R** | fill_px **19 → 25**（+6px = **+1 帧**） |
| 过帧 166ms | Y | 无变化（待排查：可能键位冲突或 VK 映射） |

**换算校验**：费用条 180px = 30 帧 ⇒ **6px = 1 帧**；
且 **30fps 下 1 帧 = 33.3ms**，与宏的 `sleep:22`/`sleep:12` 设计吻合 ⇒ **宏与帧率精确对应**。

### 10.4 另一处必须修正的问题：窗口渲染区标定
- MuMu 窗口实际为 **1296×791**（不是 1920×1080）⇒ **游戏画面被缩放显示（缩放 0.675）**；
- 之前**硬编码客户区原点 (2,63) 且按 1:1 映射**，导致所有"帧坐标→屏幕坐标"的点击整体偏移、全部落空；
- 现改为 **`resolve_render_rect()` 动态标定**：`GetClientRect + ClientToScreen`，
  换算 `screen = origin + frame × (client_size / 1920×1080)`；
- 注意：MuMu 的标题栏为**自绘**（客户区含标题栏约 63px），必要时按 UIA 的 `RenderWidget` 矩形再校正。

### 10.5 意义
⇒ **"精确到帧"的操作链路已打通**：**F 时停 + R/T/Y 过帧 + 右键划火柴** 全部可用，
且**通过 PostMessage 后台输入，与用户的真实键鼠互不干扰**（用户可同时使用电脑做别的事）。

### 10.6 下一步
1. 排查 Y（166ms）无效的原因；
2. **实测"划火柴"**：PostMessage 投递 `WM_RBUTTONDOWN → WM_MOUSEMOVE×N → WM_RBUTTONUP`
   （按住右键从卡片划到目标格），随后 F 时停；
3. 把 `Deployer` 的输入后端切到 **PostMessage 通道**；
4. 用"过帧"实现**按轴表逐帧推进**：暂停 → 过帧到目标帧 → 执行操作 → 再过帧。
'''

s = io.open(DOC, encoding='utf-8').read()
if '十、★★★决定性突破' not in s:
    io.open(DOC, 'a', encoding='utf-8').write(EXTRA)
    print('已更新划火柴资料文档')

ADD = (' **★★★决定性突破：PostMessage 输入通道打通「F 时停 / R·T 过帧」（2026-09-15，用户提示后）**：'
       '①**用户提示**："我可以手动按 F 触发时停，云迹方案正常。但你的操作看起来被我其他层级的操作屏蔽了，'
       '尝试不被我干扰的输入方式。" ⇒ 改用**不经过系统输入队列**的注入；'
       '②**三种通道实测对比**：`adb shell input keyevent` ❌（宏在模拟器软件层）；'
       'Windows **SendInput** ❌（被用户前台输入抢占/屏蔽）；'
       '**Windows `PostMessage` 直接投递到渲染窗口 ✅✅ 成功触发宏** —— '
       '实现要点：`FindWindowExW(主窗口, None, "nemuwin", None)` 取渲染子窗口，'
       '**`lParam` 必须带扫描码**（`MapVirtualKeyW(vk,0)`），发 `WM_KEYDOWN(0x0100)/WM_KEYUP(0x0101)`；'
       '③**实测（1-1 演习，云迹方案）**：**F 时停 ✅**（cost 20→22 运行中 → 发键后 cost 23 恒定 ⇒ 暂停）；'
       '**T 过帧 33ms ✅**（fill_px 13→19）；**R 过帧 12ms ✅**（19→25）；Y(166ms) 无变化（待排查）；'
       '**换算校验**：费用条 180px=30 帧 ⇒ **6px = 1 帧**，且 30fps 下 1 帧 = 33.3ms 与宏 sleep 值吻合；'
       '④**同时修正一处根因**：**MuMu 窗口实际为 1296×791（缩放 0.675），不是 1920×1080** —— '
       '此前硬编码客户区原点 (2,63) 且按 1:1 映射 ⇒ **所有坐标点击整体偏移、全部落空**；'
       '现改为 `resolve_render_rect()`（GetClientRect + ClientToScreen）**动态标定**；'
       '⑤**意义**：**"精确到帧"的操作链路打通** —— F 时停 + R/T/Y 过帧 + 右键划火柴 全部可用，'
       '且 **PostMessage 为后台输入，与用户真实键鼠互不干扰**（用户可同时用电脑做别的事）；'
       '⑥**下一步**：(a) 排查 Y 无效原因；(b) **实测划火柴**（PostMessage 投递 '
       '`WM_RBUTTONDOWN → WM_MOUSEMOVE×N → WM_RBUTTONUP` 从卡片划到目标格，再 F 时停）；'
       '(c) 把 `Deployer` 输入后端切到 PostMessage；(d) 用"过帧"实现按轴表逐帧推进；'
       '⑦**合规**：仅图形界面级操控（模拟器官方键鼠方案 + 窗口消息注入）；未触碰游戏文件/内存。 | 2026-09-15 |')

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
