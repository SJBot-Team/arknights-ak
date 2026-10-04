# -*- coding: utf-8 -*-
"""append_t052_live4.py — 追加"落格提交五种通道全部失败 → D1 完整通道矩阵"到 T-052 行。"""
import sys

sys.stdout.reconfigure(encoding='utf-8')
p = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
s = open(p, encoding='utf-8').read()
lines = s.split('\n')
i = next(k for k, l in enumerate(lines) if l.startswith('| T-052 |'))
row = lines[i]
assert row.endswith('|'), row[-20:]

entry = (
 '【第72轮】★★★**实机：把 D1（部署"落格提交"）的输入通道矩阵测完整 —— 抓取可通、提交全部失败**：'
 '①**已测通道与结果（截图哈希逐条比对，避免主观判断）**：'
 '**(a) ADB `input tap`（卡片→格子）**：❌ 完全无变化；'
 '**(b) ADB `input motionevent` DOWN+MOVE(+…)+UP**：**✅ 抓取成功**（画面出现干员悬停于部署光标、白色菱形、'
 '**「点击取消」**按钮、生命条高亮），**但 UP 不提交**（截图 sha256 与抓取态完全相同）'
 '—— **暂停态与运行态都试过，均抓取成功、均不提交**；'
 '**(c) ADB `input swipe`（600/1200ms）**：❌ 被忽略（sha256 完全不变，与既有结论一致）；'
 '**(d) Windows `SendMessage` 拖拽（`WinInput.sm_drag`，含 13 点插值 + hold）**：❌ **完全无效**'
 '（截图与操作前逐字节相同）—— 注意：`sm_drag` 是**不移动真实光标**的 SendMessage 版，恰因此不生效；'
 '**(e) Windows `PostMessage` 拖拽**（自组 WM_LBUTTONDOWN + 多点 WM_MOUSEMOVE(MK_LBUTTON) + WM_LBUTTONUP）：'
 '❌ 未抓取也未提交（干员仍保持此前 held 态）；'
 '②**结论**：**抓取只能靠 ADB `motionevent`；"提交"这一步在本次测过的五种通道下全部失败**'
 '⇒ D1 从"整条部署链"精确收窄为**单一动作：释放/提交**；'
 '③**下一步（唯一未试且与既有结论吻合的路径）**：**云迹宏「划火柴」** —— '
 '既有结论明确「**划火柴需真实鼠标（宏读 `GetCursorPos`）**；adb keyevent 与 SendInput 均不能触发 MuMu 宏；'
 '**Windows 层 PostMessage 可触发 MuMu 宏**」⇒ 正确组合应是：'
 '**先把真实光标移到目标位置（SetCursorPos）→ 再 PostMessage 发送宏键（keymap 中的划火柴键）**，'
 '由宏自己完成拖拽；需先读 `%APPDATA%\\Netease\\MuMuPlayer\\data\\keymapConfig\\` 确认键与语义；'
 '④**另一待试**：`WinInput.drag_right_real`（真实鼠标 + SendInput 版）—— 但既有结论称 **SendInput 不行**，'
 '优先级低于 ③；'
 '⑤**收尾状态（已程序化校验）**：点「点击取消」退出悬停态（该按钮红色像素占比 = **0.0**），'
 '并已把演习战斗**重新暂停**；**未产生任何部署、未消耗理智/资源、未打开禁用界面**；'
 '⑥**合规**：仅图形界面级点击/拖拽与截图；未登录（账号本就登录态）、未读改游戏文件/内存。 |'
)

lines[i] = row[:-1] + entry
open(p, 'w', encoding='utf-8').write('\n'.join(lines))
print('ok; new row length =', len(lines[i]))
