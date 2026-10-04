# -*- coding: utf-8 -*-
"""append_t052_d6ok.py — ★记录"干净重开后 axis 驱动部署在修正后的 D6 成功"。"""
import sys

sys.stdout.reconfigure(encoding='utf-8')
p = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
s = open(p, encoding='utf-8').read()
lines = s.split('\n')
i = next(k for k, l in enumerate(lines) if l.startswith('| T-052 |'))
row = lines[i]
assert row.endswith('|'), row[-20:]

entry = (
 '【第88轮】★★★★★★**干净重开演习后，「轴表 → 修正后 D6 → 两段式」实机部署成功 —— 与用户宣称的格子对齐**：'
 '①**先解决"退出"入口**：暂停后点**左上齿轮** ⇒ 弹出「**I QUIT / 作战完成度 57%**」对话框，'
 '提示「**放弃行动将会恢复0理智（全部返还）**」（演习无消耗 ✓），按钮为「返回」/「**放弃行动**」'
 '⇒ 点 (1414,859) 放弃 ⇒ 回到关卡外 ⇒ `apps/nav_to_drill.py` **9 步重进全新演习**（`battle=True`）✓；'
 '②**★轴表驱动部署**（`apps/axis_deploy_live.py 1-1 --index 0`）：'
 '轴表 `deploys[0]` = **芬 @ D6 朝左 费用 8** → `grid_px` 解 **格 (1182,502)、朝向点 (1057,502)** '
 '→ 取"费用最低的第 1 张卡" (88,1007) → **两段式**（ADB `motionevent`，拖到格松手 → 拖朝向松手）；'
 '③**★结果（截图 `ak/.tmp/axisdep_D6.png` 逐项确认）**：'
 '**「剩余可放置角色：8 → 7」** ✓；**芬的 8 费卡片从卡槽消失**'
 '（卡槽变为 9,9,9,13,14,15,15,16,16,17，其中 14 = 月见夜仍在）✓；'
 '**芬出现在地图上**（蓝发猫耳持枪），位置在走廊 **col≈4.6~5 ⇒ 即 D6** ✓，'
 '且**朝向箭头指向左侧**（对应轴表"朝左"）✓，并**正在阻挡一只敌人** ✓；'
 '④**费用读数"只降 5"已解释**：操作期间游戏仍在运行（约 3 秒 ⇒ 回费 +3），'
 '而部署扣 8 ⇒ 净 **−5**（22→17）⇒ 与"部署成功"一致；'
 '⑤**⇒ 至此贯通**：**格点命名（Excel 宏表口径 rc_normal）→ 格像素（grid_px 唯一真源）'
 '→ 朝向语义 → 两段式拖拽 → 提交** 全链路在实机成立；'
 '**此前长期卡点 D1（落格提交）彻底关闭**；'
 '⑥**合规**：仅界面级点击/拖拽/暂停与截图；对话框明确「恢复0理智（全部返还）」⇒ **演习零消耗**；'
 '未登录、未读改游戏文件/内存。 |'
)

lines[i] = row[:-1] + entry
open(p, 'w', encoding='utf-8').write('\n'.join(lines))
print('ok; new row length =', len(lines[i]))
