# -*- coding: utf-8 -*-
"""append_t052_chain.py — ★记录"轴表→OCR选卡→两段式部署"全链路实机打通。"""
import sys

sys.stdout.reconfigure(encoding='utf-8')
p = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
s = open(p, encoding='utf-8').read()
lines = s.split('\n')
i = next(k for k, l in enumerate(lines) if l.startswith('| T-052 |'))
row = lines[i]
assert row.endswith('|'), row[-20:]

entry = (
 '【第99轮】★★★★★★**「轴表 → 费用预测位次 → 名称OCR自校验 → 两段式拖拽部署」全链路实机打通**：'
 '①**新增 `code/vision/apps/card_select.py`**：`select_card_by_name(cap, dep, target, plan, deployed, try_first)` —— '
 '**先点"费用预测位次"的卡片，再依次扫其余**；每次「点卡 → 抓图 → `read_selected_name()` 读面板名 → 与目标比对」，'
 '命中即返回该卡像素中心；并附 `card_centers()`（`find_cards` 不足时用均匀网格补全）；'
 '**⇒ 同时满足用户指出的三点**：练度影响费用（费用仅作**起点**、不作判据）、同费用不唯一（本编队 3 人同为 9 费）、'
 '局内费用可变；②**接入 `apps/axis_deploy_live.py`**（替换原费用选卡）：'
 '`axis yaml 的 op 名 → card_plan 费用预测位次 → select_card_by_name（OCR 自校验）→ deploy_two_step_px`；'
 '③**★实机结果（1-1 演习，全新一场）**：'
 '自动导航 9 步进战斗 → 费用 13（够 8 费）→ **费用预测位次 = 0** → '
 '**`卡#0 (x=148) → OCR 名=\'芬\' ✅ 命中`（一次命中）** → 两段式部署（卡(148,1007) → 格(1182,502) → 朝向点(1057,502)）；'
 '**截图逐项确认**：**「剩余可放置角色：8 → 7」** ✅；**芬的 8 费卡片从卡槽消失**'
 '（现为 9,9,9,13,14,15,15,16,16,17）✅；**芬出现在走廊上**、**方向箭头指向左**（对应轴表"朝左"）✅、'
 '**正在阻挡一只敌人** ✅；**费用 15 → 11 = −8（部署）+ 4（4 秒回费）** ✅ 精确吻合；'
 '④**⇒ 至此打通的目标②链路**：'
 '**共用轴表 → 格子命名（Excel 口径）→ 格像素（`grid_px` 唯一真源）→ 朝向语义 → '
 '干员卡片识别（名称 OCR，借鉴 MAA 的 OCR 路线）→ 两段式拖拽 → 落格提交（费用/卡槽双证据）**；'
 '⑤**残留问题（已定位，下一轮）**：**落点仍偏约 0.6 格**（本次芬实际在 col≈4.4，目标 D6 = col 5；'
 '第 88 轮那次偏差 0.4 格）—— 与此前"第二段朝向拖拽**跨了整整一格**"的猜想一致'
 '（游戏内"定朝向"只需小幅拖拽，跨格可能被解释为移动/重选格）；'
 '**验证方法**：把朝向拖拽改为**小幅偏移（40~60px）**，再看落点是否精确落在目标格中心；'
 '⑥**合规**：仅界面级点击/拖拽/暂停与截图 + 只读 OCR；对话框确认「放弃行动恢复 0 理智（全部返还）」⇒ 演习零消耗；'
 '未登录、未读改游戏文件/内存。 |'
)

lines[i] = row[:-1] + entry
open(p, 'w', encoding='utf-8').write('\n'.join(lines))
print('ok; new row length =', len(lines[i]))
