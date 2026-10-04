# -*- coding: utf-8 -*-
"""append_t052_macro.py — 追加"宏语义解析 + 真实鼠标拖拽通道"到 T-052 行。"""
import sys

sys.stdout.reconfigure(encoding='utf-8')
p = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
s = open(p, encoding='utf-8').read()
lines = s.split('\n')
i = next(k for k, l in enumerate(lines) if l.startswith('| T-052 |'))
row = lines[i]
assert row.endswith('|'), row[-20:]

entry = (
 '【第81轮】★★★★**键鼠方案宏语义完全解析 + 首次使用"真实鼠标拖拽"通道；D1（释放提交）仍是唯一缺口**：'
 '①**新增 `apps/find_drag_macro.py` 与 `.tmp/dump_keymap2.py`（只读解析）**：修正 `keymaps` 结构展开'
 '（`keymaps` 是列表，元素为 dict，其 values 才是按键条目）；'
 '②**★宏语义完全解析**（`com.YoStarJP.Arknights-F键时停方案（划火柴）.json`，动作词表 = '
 '`click_rel / sleep / keyboard_press / keyboard_release`）：'
 '**`F`** = `keyboard_press:158`（Android **KEYCODE_BACK**）/ 抬起 `keyboard_release:158`；'
 '**`S`** = `click_rel:(0.9369,0.0778)`【**即右上暂停按钮**】+ `sleep:5` + **`click_rel:mouse`** + `sleep:5` + BACK；'
 '**`W`** = `click_rel:(0.9406,0.0744)` + `sleep:50` + BACK；'
 '③**★关键推论**：`S` 的第一个动作是**点暂停按钮** —— 而上一轮已实测"悬停态点暂停按钮会取消悬停"'
 '⇒ **`S` 不是落格宏**（它先取消再点击，自然什么都不发生）；'
 '**且整套键鼠方案里没有任何"拖拽"动作** ⇒ **"划火柴"本身就是真实鼠标拖拽**'
 '（宏层把**真实鼠标的按下—移动—抬起**翻译成触摸拖拽），这与既有结论「划火柴需真实鼠标」一致；'
 '④**★`F` 键可用于恢复运行**：实测发 `F` 后相位速率 0 → **22 帧/秒** ⇒ 宏"时停"是**按一下暂停/再按一下恢复**；'
 '⑤**★首次使用"真实鼠标拖拽"通道（`apps/real_drag.py`）**：'
 '`SetCursorPos` + `mouse_event(LEFTDOWN)` → 沿路径移动 → `LEFTUP`：'
 '**抓取成功** ✓（干员悬停、出现「点击取消」、剩余区 84.3→52.7）'
 '**但抬起仍不被接受**；'
 '⑥**运行态"快速"真实拖拽（≈0.2s，即"划火柴"本体，`apps/real_drag_run.py`）**：'
 '先取消悬停 → 宏键 F 恢复运行（0→22 帧/秒）→ 快速真实拖拽 ⇒ **仍在悬停**（剩余区 58.1）'
 '⇒ **运行态同样只在"抓取"成功、"抬起"不生效**；'
 '⑦**⇒ D1 精确现状**：**"抓取"在全部通道可用**'
 '（ADB `motionevent`、真实鼠标拖拽），**"抬起/提交"在全部通道均不被接受**，已穷尽：'
 'ADB `tap` / `motionevent UP` / `swipe`、Windows `SendMessage` 拖拽、`PostMessage` 鼠标拖拽、'
 '宏键 `click_rel:mouse` 点击、**真实鼠标拖拽（暂停态 + 运行态）**；'
 '⑧**流程 ①→④ 已全部打通**（费用条满条计数与双通道互证、子弹时间 5.0×、过帧窗口、宏键暂停且保留悬停）；'
 '**唯 ⑤ 待解** ⇒ 已向用户询问"落格提交"的确切手法（用户熟悉"划火柴/0 帧操作"）；'
 '⑨**合规**：仅界面级鼠标/点击与截图 + 只读解析；未登录、全程演习未消耗理智、未读改游戏文件/内存。 |'
)

lines[i] = row[:-1] + entry
open(p, 'w', encoding='utf-8').write('\n'.join(lines))
print('ok; new row length =', len(lines[i]))
