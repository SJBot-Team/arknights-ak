# -*- coding: utf-8 -*-
"""append_t052_hold.py — 追加"悬停态门控 bug + 实机首次测到 1X 帧率"到 T-052 行。"""
import sys

sys.stdout.reconfigure(encoding='utf-8')
p = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
s = open(p, encoding='utf-8').read()
lines = s.split('\n')
i = next(k for k, l in enumerate(lines) if l.startswith('| T-052 |'))
row = lines[i]
assert row.endswith('|'), row[-20:]

entry = (
 '【第79轮】★★★★★**实机探针暴露门控真 bug（悬停操作态被误判为非战斗）并修复；顺带首次精确测到 1X 帧率 30.1**：'
 '①**新增工具 `apps/bullet_time_probe.py`**（验证用户方案第②步"子弹时间"）：'
 '用**费用条相位推进速率**当"游戏时间流速"的度量 —— 先测**基线**，再 `Deployer.motion` **拖出干员（悬停不落格）**'
 '后测**悬停段**，给出减速比；`apps/nav_check.py` 为逐步导航提供只读信号（battle/cards/按钮亮度）；'
 '②**★实机首次精确测到 1X 帧率**：基线 **8.39s 内推进 240 帧 ⇒ 30.1 帧/秒**（满条 8 次）'
 '—— 与"1 次满条 = 30 帧"完全一致，**独立佐证费用条时钟的绝对时间口径**；'
 '③**★★真 bug（由实机探针暴露）**：悬停段**样本数 0** ⇒ 追查发现 **`BattleHudGate` 把"操作中的战斗"误判为非战斗**；'
 '**根因**：**拖出干员悬停时底部卡片行会隐藏** ⇒ 三路信号里的"卡片行"失效 ⇒ '
 '**门控会在最需要计时的时刻（正要做帧级操作时）停止采样**；'
 '④**修复**：`BattleHudGate` 新增**第 4 路信号「点击取消」红色按钮**（`HOLD_ROI=(690,266,774,342)`），'
 '判据 `in_battle = (卡片行 ∧ 费用数字 ∧ 敌人计数) ∨ 悬停`；'
 '**阈值经实测定为 ≥0.40**：该 ROI 红色占比实测 —— **悬停态 0.762**、正常战斗 0.000、'
 '**编队页 0.053**、**主界面 0.116** ⇒ 清晰可分（首版取 0.05 曾把编队页/主界面误判为战斗，已修正）；'
 '⑤**门控回归 12/12 通过**（新增 3 个**悬停态正样本** `live_14_drag / live_20_running_drag / live_21_postmsg`，'
 '另加 `live_18_smdrag` 为常规战斗正样本）；端到端佐证仍成立（失败页给出 `frame=29` 伪读数 ⇒ 被拦下）；'
 '⑥**探针的结论逻辑也修正**：样本数为 0 时**必须判"测量失败"**，不得据此宣称"子弹时间成立"'
 '（首版曾给出错误的 ✅ 结论）；'
 '⑦**遗留**：**子弹时间本体待重测** —— 本轮战斗在修改代码期间被结束（回到章节地图），'
 '下一轮按 `nav_check` 逐级校验后重跑 `bullet_time_probe`；'
 '⑧**合规**：仅图形界面级点击/拖拽与截图 + 只读识别；未登录、全程演习未消耗理智、未读改游戏文件/内存。 |'
)

lines[i] = row[:-1] + entry
open(p, 'w', encoding='utf-8').write('\n'.join(lines))
print('ok; new row length =', len(lines[i]))
