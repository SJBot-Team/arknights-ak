# -*- coding: utf-8 -*-
"""append_t052_wf.py — 追加"子弹时间实测 5× + 宏键通道打通 + 流程①→④闭环"到 T-052 行。"""
import sys

sys.stdout.reconfigure(encoding='utf-8')
p = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
s = open(p, encoding='utf-8').read()
lines = s.split('\n')
i = next(k for k, l in enumerate(lines) if l.startswith('| T-052 |'))
row = lines[i]
assert row.endswith('|'), row[-20:]

entry = (
 '【第80轮】★★★★★**子弹时间实测成立（5.0×）；`PostMessage` 宏键通道打通；用户流程①→④闭环，仅剩⑤提交**：'
 '①**新增 `apps/nav_to_drill.py`（带信号校验的自动导航）**：按状态机逐步前进 —— '
 '`btn_drill≥170`=关卡详情页、`110~170`=编队页、`<110`=章节地图、均值<60=加载/结算；'
 '**实测 6 步从章节地图进入战斗**（map→stage→squad→loading→loading→**battle**）✓；'
 '②**★★子弹时间实测成立（用户方案第②步）**：`apps/bullet_time_probe.py` —— '
 '**基线 30.3 帧/秒 → 拖出干员悬停 6.1 帧/秒，减速比 ≈ 5.0×** '
 '（1X 下单帧 33ms，减速后 ~164ms）⇒ **"过帧 + 暂停定位"具备逐帧窗口** ✓；'
 '③**★★`PostMessage` 宏键通道打通（新能力）**：`WinInput.post_key("f")` 后'
 '**费用条相位冻结在 7、fill_px 恒定** ⇒ **宏"时停"确实暂停了游戏**；'
 '⇒ 这给"暂停定位"提供了**不依赖点按钮**的可靠手段；'
 '④**★★关键差异（本轮新发现）**：**悬停态下点"暂停按钮"会立刻取消悬停**'
 '（实测剩余区亮度 52.7 → 84.3、hold 0.762 → 0）；而**用宏键 F 暂停则悬停保留**'
 '（`hold=0.762` 前后不变）⇒ 用户方案的顺序「悬停(子弹时间) → 宏键暂停 → 释放」**首次变得可行**；'
 '⑤**新增 `apps/workflow_try.py`（走完用户流程 ②~⑤）**：实测为 —— '
 '起点 in_battle=True → 拖出干员 `hold=0.762`（子弹时间）→ 宏键 F 暂停后 `hold=0.762`（**悬停保留** ✓）'
 '→ 在"暂停+悬停"态尝试释放（`motionevent UP` + 补 `tap`）→ **hold 仍 0.762，未被接受** ✗；'
 '⑥**宏自身点击也试过**：`SetCursorPos` 把真实光标移到 D6 屏幕坐标 (661,402) 后发宏键 `s`/`w`（该方案中含 '
 '`click_rel:mouse`）⇒ **悬停结束（hold=0）但截图确认：仍在暂停、剩余可放置角色仍为 8、'
 '芬的卡片仍可用、地图上无芬** ⇒ **宏点击只是"取消拖拽"，并未落格**；'
 '⑦**⇒ D1 现状（精确刻画）**：**流程①→④已全部打通**'
 '（①费用条满条计数+双通道互证 ✓ ②子弹时间 5× ✓ ③过帧窗口具备 ✓ ④宏键暂停定位且保留悬停 ✓），'
 '**唯独 ⑤"释放→提交"仍未被任何通道接受** —— 已试：ADB `tap`/`motionevent UP`/`swipe`、'
 'Windows `SendMessage` 拖拽、`PostMessage` 鼠标拖拽、宏键 `click_rel:mouse` 点击；'
 '**下一步应找宏里真正做"拖拽"的动作**（`curve_rel:mouse` 之类，即"划火柴"本体），'
 '而不是 `click_rel:mouse`（点击）；'
 '⑧**收尾状态**：游戏处于**宏暂停**（相位冻结、无时间推进）；**未产生任何部署、未消耗理智/资源**；'
 '⑨**合规**：仅图形界面级点击/拖拽/截图 + 只读识别；宏键为**模拟器键鼠方案**（非游戏文件/内存）；未登录。 |'
)

lines[i] = row[:-1] + entry
open(p, 'w', encoding='utf-8').write('\n'.join(lines))
print('ok; new row length =', len(lines[i]))
