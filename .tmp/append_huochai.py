# -*- coding: utf-8 -*-
"""append_huochai.py — ★★划火柴：从官方/MuMu 宏中提取的完整实现资料与设计。"""
import io
import os
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')

DOC = r'C:\Users\23922\Documents\ds_harness\ak\knowledge\04_数据对应与核验\51_划火柴_暂停态精确部署_实现资料.md'
REG = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
DST = r'E:\__file\ak_kb\kb'

MD = '''# 「划火柴」：暂停态精确部署 —— 现成实现的完整资料与本方设计

> 来源（用户指引："明日方舟要精确到帧级部署，比如暂停时部署，需要用到划火柴技巧。AFA 有现成的宏"）：
> 1. **MuMu 官方帮助**《明日方舟》划火柴按键全操作教学 —— https://mumu.163.com/help/20230705/35048_1097000.html
> 2. **本机 MuMu 键鼠方案**（39 个）位于
>    `%APPDATA%\\Netease\\MuMuPlayer\\data\\keymapConfig\\*.json`，其中直接就有
>    **`com.YoStarJP.Arknights-F键时停方案（划火柴）.json`** 与 **`com.hypergryph.arknights-默认操作方案.json`**。

## 一、官方教程要点（MuMu 12 3.3.5+ 默认键鼠方案）

| 键 | 功能 | 官方说明 |
|---|---|---|
| **F** | **时停操作** | "先鼠标点击干员头像，后按 F 键，**游戏战斗进程停止，但鼠标仍可以拖放干员调整位置**" |
| G | 普通暂停 | — |
| **W** | **划火柴（0 帧部署）** | "先按 F 或 G 暂停，然后点击 W，**等待 0.1s**，再**快速从干员区拖出目标干员**"；**建议 1 倍速** |
| **S** | **0 帧选取** | "先按 F/G 暂停，鼠标放在干员位置，点击 S 即可选中干员" |
| E | 卡帧对轴 | — |
| A / D / Q | 一键撤退 / 一键技能 / 撤退 | — |
| 空格 | 切换倍速 | — |
| C | 鼠标点击 | 点击后自动点击鼠标指向位置 |
| \\` | 返回 | — |

**★关键机制**：**暂停后"鼠标仍可拖放干员"** ⇒ 这正是"暂停态精确部署"得以成立的原理。

## 二、宏的实际实现（从本机方案 JSON 提取，可直接照抄）

### 2.1 官方默认方案 `com.hypergryph.arknights-默认操作方案.json`

**`[0帧部署（划火柴）]`  type=Macro  触发键 = 鼠标右键（vk=2）**
```
press: [
  'release_all',
  'mouse_release:1',
  'keyboard_press:11', 'keyboard_release:11', 'keyboard_release:11',
  'curve_first_point_sleep_time:17',
  'curve_last_point_sleep_time:until_release_cmd',
  'curve_rel:mouse;(2.714441, 4.826255)',      ← ★ 鼠标"划"的曲线（相对倍率）
  'mouse_press:1',                              ← ★ 按住左键
  'keyboard_press:158', 'keyboard_release:158', 'keyboard_release:158'  ← ★ 发送"时停键"
]
release: ['release_all', 'mouse_release:1']
```

**`[W = 划火柴]`（F 键时停方案中）**
```
press: ['click_rel:(0.940625, 0.07444444444444444)',   ← 点"暂停"按钮
        'sleep:50',                                     ← ★ 等 50ms（官方说的 0.1s）
        'keyboard_press:158']                           ← 发送时停键
release: ['keyboard_release:158']
```

**`[F = 时停]`**：`press: ['keyboard_press:158']` / `release: ['keyboard_release:158']`

**`[S = 0帧选取]`**
```
press: ['click_rel:(0.936875, 0.07777777777777778)',  ← 点暂停
        'sleep:5', 'click_rel:mouse',                  ← 点鼠标当前位置（选中干员）
        'sleep:5', 'keyboard_press:158']
release: ['keyboard_release:158']
```

**`[E = 卡帧对轴]`**：`press: ['click_rel:(0.936270,0.078333)', 'sleep:99', 'keyboard_press:158', 'keyboard_release:158']`

**`[G = 暂停]`**：`Click`，rel=(0.9231, 0.0778)
**`[A = 一键撤退]`**：`press: ['click_rel:mouse', 'sleep:100', 'click_rel:(0.476250,0.305556)']`
**`[D = 一键技能]`**：`press: ['click_rel:mouse', 'sleep:100', 'click_rel:(0.665000,0.542222)']`

### 2.2 三条可直接复用的结论
1. **"时停" = 发送按键 `158`**（Every宏的公共动作；对应返回/ESC 语义）
2. **"暂停按钮" 相对坐标 rel≈(0.9406, 0.0744)** ⇒ 帧 **≈(1806, 80)**
   —— **与 MAA 的 `BattleHasStarted` roi 换算 (1807,79) 完全一致**（两条独立来源互相印证）
3. **"划火柴"的时序**：`按住左键 → 曲线移动到目标格 → 松开`，且**期间/之后发送时停键**

## 三、本方的关键实测（2026-09-15）

- **`adb shell input keyevent`（ESC=111 / BACK=4）无法触发 MuMu 的键鼠宏** —— 宏运行在**模拟器软件层**，
  必须用 **Windows 层**的键盘/鼠标注入（如 SendInput / SendKeys）才能触发；
- 因此**本方实现路线**：**Windows 层注入鼠标拖拽 + 键盘宏键**，而不是继续拼 `adb motionevent`；
- 副作用提醒：MuMu 被遮挡时会停止渲染 ⇒ 注入前需**确保窗口在前台**（`EmuWindowCapture.bring_to_front()` 或激活窗口）。

## 四、本方"划火柴"实现设计（下一步落地）

```
deploy_huochai(card_rel_xy, grid_frame_xy, direction):
  1. 确保 MuMu 窗口在前台（否则渲染停止、注入无效）
  2. 暂停（两种可选）：
     a) Windows 层发 F 键（时停宏）—— 官方推荐
     b) 或点击暂停按钮 帧(1806,80)  【已多次验证可用】
  3. 选中卡片：Windows 层"移动到卡片 → 按下左键"（或发送 S 宏做 0 帧选取）
  4. 划火柴：保持左键，**曲线移动**到目标格（可分若干中间点模拟 curve），松开
  5. 期间/结束后发送时停键（158 对应键），确保游戏停在暂停态
  6. 校验：读"剩余可放置角色"计数（8→7）、卡片消失、费用扣除
```

**注意**：本方的目标是"**把轴表里的操作精确落到指定帧**"，因此最终形态应当是
**"暂停 →（在暂停态完成全部操作）→ 按相位对齐恢复"**，即
**一次暂停内完成同帧多操作**（这正是"同帧多操作"需求的实现路径）。

## 五、待办
1. 用 Windows 层注入实测 F 键（时停）是否生效（需在**战斗中**验证，当前 TR-1 已结束）；
2. 实测"按住左键 → 曲线移动 → 松开"的划火柴是否完成部署；
3. 若可行，把 `Deployer` 的输入后端从 `adb motionevent` 切换为 **Windows 层注入**；
4. 与模拟器的"同一帧多操作"对照（切片里的 `ops` 字段已保存同帧操作顺序）。
'''

io.open(DOC, 'w', encoding='utf-8').write(MD)
print('已写出划火柴实现资料:', DOC)

ADD = (' **★★划火柴（暂停态精确部署）：从官方/MuMu 宏提取到完整实现资料（2026-09-15，用户指引）**：'
       '①**来源**：(a) **MuMu 官方帮助《明日方舟》划火柴按键全操作教学**；'
       '(b) **本机 39 个键鼠方案**（`%APPDATA%\\Netease\\MuMuPlayer\\data\\keymapConfig\\`），'
       '其中直接有 **`com.YoStarJP.Arknights-F键时停方案（划火柴）.json`** 与 **`com.hypergryph.arknights-默认操作方案.json`**；'
       '②**官方机制要点**：**F=时停**（"先点干员头像，后按 F，**游戏战斗进程停止，但鼠标仍可拖放干员**"）；'
       '**W=划火柴（0帧部署）**（"先按 F/G 暂停 → 点 W → **等 0.1s** → **快速从干员区拖出干员**"，建议 1 倍速）；'
       'S=0帧选取；E=卡帧对轴；**⇒ "暂停后鼠标仍可拖放干员"正是暂停态部署成立的原理**；'
       '③**★从方案 JSON 提取到宏的完整实现（可直接照抄）**：'
       '**(a) 0帧部署（划火柴）**（鼠标右键触发）：'
       '`release_all → mouse_release:1 → keyboard_press:11 → '
       'curve_first_point_sleep_time:17 → curve_last_point_sleep_time:until_release_cmd → '
       'curve_rel:mouse;(2.714441,4.826255) → mouse_press:1 → keyboard_press:158`；'
       '**(b) W（划火柴）**：`click_rel:(0.940625,0.074444) → sleep:50 → keyboard_press:158`；'
       '**(c) F（时停）**：`keyboard_press:158`；'
       '**(d) S（0帧选取）**：点暂停 → sleep:5 → 点鼠标位置 → sleep:5 → 时停；'
       '**(e) E（卡帧对轴）**：点暂停 → sleep:99 → 时停；'
       '④**三条可复用结论**：**"时停"= 发送按键 158**；**暂停按钮 rel≈(0.9406,0.0744) ⇒ 帧 ≈(1806,80)**'
       '（**与 MAA `BattleHasStarted` 换算的 (1807,79) 完全一致，两条独立来源互证**）；'
       '**划火柴时序 = 按住左键 → 曲线移动到目标格 → 松开（并发送时停键）**；'
       '⑤**本方实测的重要发现**：**`adb shell input keyevent`（ESC/BACK）无法触发 MuMu 的键鼠宏** —— '
       '宏运行在**模拟器软件层**，**必须用 Windows 层的键盘/鼠标注入**；'
       '⇒ **本方实现路线确定**：改用 **Windows 层注入**（SendInput/SendKeys + 鼠标拖拽）复现划火柴，'
       '而非继续拼 `adb motionevent`；注意注入前须确保 **MuMu 窗口在前台**（否则渲染停止）；'
       '⑥**产出 `knowledge/04/51_划火柴_暂停态精确部署_实现资料.md`**（含官方要点、宏原文、结论、本方设计与待办）；'
       '⑦**下一步**：(a) 在**战斗中**用 Windows 层发 F 键验证时停；(b) 实测"按住左键→曲线移动→松开"完成部署；'
       '(c) 把 `Deployer` 输入后端切到 Windows 层；(d) 与模拟器"同帧多操作"对照；'
       '⑧**合规**：仅图形界面级操控（模拟器的官方键鼠方案 + Windows 层注入）；未触碰游戏文件/内存。 | 2026-09-15 |')

r = io.open(REG, encoding='utf-8').read()
ra = '\n\n## 冲突记录'
r = r.replace(ra, ADD + ra, 1)
io.open(REG, 'w', encoding='utf-8', newline='').write(r)
print('台账已记录')
shutil.copy2(DOC, os.path.join(DST, 'knowledge', '04_数据对应与核验', os.path.basename(DOC)))
shutil.copy2(r'C:\Users\23922\Documents\ds_harness\ak\sim\draft\dump_keymap.py',
             os.path.join(DST, r'sim\draft\dump_keymap.py'))
shutil.copy2(REG, os.path.join(DST, 'management', 'tasks_registry.md'))
print('同步完成')
