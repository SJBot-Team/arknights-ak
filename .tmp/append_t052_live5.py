# -*- coding: utf-8 -*-
"""append_t052_live5.py — 追加"键鼠方案只读摸底：宏用 click_rel:mouse"到 T-052 行。"""
import sys

sys.stdout.reconfigure(encoding='utf-8')
p = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
s = open(p, encoding='utf-8').read()
lines = s.split('\n')
i = next(k for k, l in enumerate(lines) if l.startswith('| T-052 |'))
row = lines[i]
assert row.endswith('|'), row[-20:]

entry = (
 '【第72轮·续】★★★★**只读摸底 MuMu 键鼠方案：找到"划火柴"宏的确切动作语义 ⇒ 下一轮配方明确**：'
 '①**新增只读工具** `ak/.tmp/dump_keymap.py`（解析 MuMu 键鼠方案 JSON，**不触碰游戏文件**）；'
 '②**扫描结果**：`%APPDATA%\\Netease\\MuMuPlayer\\data\\keymapConfig\\` 下有 **40 份方案**，其中'
 '**`com.YoStarJP.Arknights-F键时停方案（划火柴）.json`** 明确以"划火柴"命名；'
 '③**★关键结构**：方案顶层 = `{info, keymaps, param}`，`keymaps` 含 **9 组**，每条 = '
 '`{key:{device,scan_code,text,virtual_key}, press_actions:[...], release_actions:[...], icon:{rel_position}}`；'
 '**动作是字符串指令**，样例（S 键）：'
 '`["click_rel:(0.936875,0.077778)", "sleep:5", "click_rel:mouse", "sleep:5", "keyboard_press:158"]`；'
 '④**★推论（决定性）**：宏动作里出现 **`click_rel:mouse`** —— 即"**在真实光标位置点击**"'
 '（`click_rel:(fx,fy)` 是屏幕相对坐标，`click_rel:mouse` 读的是 **`GetCursorPos`**）'
 '⇒ **完全印证**既有结论「**划火柴需真实鼠标（宏读 `GetCursorPos`）**」；'
 '⑤**⇒ 下一轮的确定配方**：**先把真实光标 `SetCursorPos` 到目标位置 → 再 `PostMessage` 发送宏键**'
 '（键由 `key.scan_code` / `virtual_key` 给出），由**宏自己**完成拖拽/落格；'
 '若该路仍不通，则改为"**选中卡片后 PostMessage 宏键（click_rel:mouse 落在格子上）**"的窄化版本；'
 '⑥**本轮收尾状态**：已「点击取消」退出悬停态（红色像素占比 0.0）并**重新暂停**演习战斗；'
 '**未产生任何部署、未消耗理智/资源、未打开禁用界面**；'
 '⑦**合规**：键鼠方案 JSON 属**本机模拟器配置文件（非游戏文件、非内存）**，只读；'
 '全程仅图形界面级点击/拖拽与截图。 |'
)

lines[i] = row[:-1] + entry
open(p, 'w', encoding='utf-8').write('\n'.join(lines))
print('ok; new row length =', len(lines[i]))
