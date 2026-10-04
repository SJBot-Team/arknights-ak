# -*- coding: utf-8 -*-
"""append_r9.py — 记录：PostMessage 键盘打通、坐标标定修正、F 为切换键、划火柴需真实鼠标。"""
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

## 十一、输入通道的最终分工与"时停"语义（2026-09-15 续）

### 11.1 通道分工（实测结论）
| 用途 | 通道 | 原因 |
|---|---|---|
| **键盘宏（F 时停 / R·T·Y 过帧 / W 暂停选中 / Z 子弹时间…）** | **`PostMessage` 后台投递** | 键盘宏**生效**（已实测），且**不干扰用户的真实键鼠** |
| **鼠标划火柴（右键按住滑动）** | **真实鼠标**（`SetCursorPos` + `SendInput`） | 划火柴宏依据 `curve_rel:mouse;(3.406,6.053)`，读的是**真实鼠标位移**；`WM_MOUSEMOVE` 消息**无效**（已实测） |

### 11.2 "时停"的语义（重要修正）
云迹方案的 F 宏定义为：
```
press  : ['keyboard_press:158']
release: ['keyboard_release:158']
```
⇒ **按下 F 进入时停、松开 F 恢复** ⇒ **F 不是"切换"，而是"按住期间保持"**。

由此解释了两轮实测现象：
- 上一轮"发一次 F（down+up）后 cost 恒定" ⇒ 实际是**那一次恰好把"运行"变成了"暂停"**（切换式观感）；
- 本轮"在已暂停状态下再发一次 F" ⇒ **恢复运行**（cost 23→26）⇒ 与"按住/松开"语义一致
  （快速 down+up 等价于"瞬间暂停后再恢复"，但游戏侧表现为状态翻转）。

**⇒ 正确用法：`keydown F`（保持按下）→ 完成操作 → `keyup F`**，
这样整个"划火柴 + 定位 + 执行"过程都停在暂停态 —— **正是"操作前先步进、定位到帧后再执行"的实现方式**。

### 11.3 坐标标定（★根因修正）
- MuMu 窗口实际 **1296×791**（游戏画面被缩放，**缩放系数 0.675**）；
- 且其**标题栏为自绘**（客户区包含顶部约 **63px** 的非画面区域）；
- ⇒ 渲染区 = **屏幕原点 (5, 84)、尺寸 1296×728**；
- 换算：`screen = origin + frame × (rendered_size / 1920×1080)`。
- **此前硬编码 (2,63) 且按 1:1 映射 ⇒ 所有坐标点击整体偏移、全部落空**（这是多轮"点了没反应"的另一半根因）。

### 11.4 本轮实测
| 试验 | 结果 |
|---|---|
| PostMessage 发 **F**（1-1 演习，运行中） | ✅ **cost 20→22 停在 23 恒定 ⇒ 暂停** |
| PostMessage 发 **T(33ms)** | ✅ fill_px 13→19（**+6px = +1 帧**） |
| PostMessage 发 **R(12ms)** | ✅ fill_px 19→25（+1 帧） |
| PostMessage 发 Y(166ms) | ❌ 无变化（待查，可能键位冲突/VK 映射） |
| PostMessage 右键拖拽（划火柴） | ❌ 无效果（宏读真实鼠标位移） |
| **真实鼠标右键拖拽**（在暂停态） | ❌ 过程中**游戏恢复了运行**（cost 40→42）⇒ 需改为"**按住 F**"保持暂停 |

### 11.5 下一步（明确）
```
1. keydown F（PostMessage，保持按下）        ⇒ 全程保持时停
2. 真实鼠标：移到卡片 → 右键按下 → 划到目标格 → 右键松开   ⇒ 划火柴
3. （若需定朝向）拖动白色菱形
4. keyup F                                    ⇒ 恢复
5. 校验：可放置数 −1 / 卡片消失 / 费用扣除；并记录"操作发生的游戏内帧"
6. 用 R/T/Y 过帧把操作精确推到轴表要求的帧
```
'''

s = io.open(DOC, encoding='utf-8').read()
if '十一、输入通道的最终分工' not in s:
    io.open(DOC, 'a', encoding='utf-8').write(EXTRA)
    print('已更新资料文档')

ADD = (' **输入通道分工与「时停」语义修正 + 坐标标定根因（2026-09-15）**：'
       '①**通道分工确定**：**键盘宏（F/R/T/Y/W/Z）用 `PostMessage` 后台投递**（已实测生效，'
       '且不干扰用户真实键鼠）；**鼠标划火柴必须用真实鼠标**（宏依据 `curve_rel:mouse` 读真实位移，'
       '`WM_MOUSEMOVE` 消息无效，已实测）；'
       '②**★「时停」语义修正**：云迹 F 宏为 `press: keyboard_press:158` / `release: keyboard_release:158` '
       '⇒ **按下 F 进入时停、松开恢复**，而非"切换"；由此解释了两轮现象（上一轮快速 down+up 恰好把运行变暂停；'
       '本轮在已暂停时再按 F 反而恢复运行 cost 23→26）⇒ **正确用法：`keydown F` 保持 → 操作 → `keyup F`**，'
       '这正是"操作前先步进、定位到帧后再执行"的实现方式；'
       '③**★坐标标定根因修正**：MuMu 窗口实际 **1296×791（游戏画面缩放 0.675）**，'
       '且**标题栏为自绘（客户区含顶部约 63px 非画面区）** ⇒ 渲染区 = **(5,84) 1296×728**；'
       '此前硬编码 (2,63) 且 1:1 映射 ⇒ **所有坐标点击整体偏移、全部落空**（多轮"点了没反应"的另一半根因）；'
       '现 `resolve_render_rect()` 已改为 **GetClientRect + ClientToScreen + 标题栏校正**；'
       '④**本轮实测**：PostMessage F ✅（暂停）；T(33ms) ✅ fill_px 13→19（**+6px = +1 帧**）；R(12ms) ✅ 19→25；'
       'Y(166ms) ❌ 无变化（待查）；PostMessage 右键拖拽 ❌；**真实鼠标右键拖拽在暂停态失败**'
       '（过程中 cost 40→42 恢复运行）⇒ 需改为"**按住 F**"保持暂停；'
       '⑤**下一步（明确）**：`keydown F → 真实鼠标划火柴（卡片→目标格）→（可选定朝向）→ keyup F '
       '→ 校验可放置数/卡片/费用 + 记录操作的游戏内帧 → 用 R/T/Y 过帧把操作精确推到轴表要求的帧`；'
       '⑥**合规**：仅窗口消息注入 + 模拟器官方键鼠方案 + 真实鼠标（短时）；未触碰游戏文件/内存。 | 2026-09-15 |')

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
