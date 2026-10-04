# -*- coding: utf-8 -*-
"""update_t052_round30.py — 写入 T-052 第三十轮（实机锚定测量：敌人流水线偏快 19%）。"""
import io
import sys

sys.stdout.reconfigure(encoding='utf-8')

P = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
ADD = (
    ' **第三十轮（实机锚定测量：敌人流水线偏快 ≈19%）**：'
    '①建立**可复用的实机测量范式** `code/vision/apps/run_drill_and_measure.py`（点「开始行动」后立刻 2s 一次截屏，'
    '同时裁顶部 HUD 与右下费用区拼时间轴），**用费用数字当绝对时间锚**：费用 10 起 1/s 上涨 ⇒ 截到「费用<20」即有 t=费用−10；'
    '②**实测（演习、1× 速度、不部署任何干员）**：费用 10→12→14→…→20 MAX 与偏移拟合 11.5±0.5s 完全吻合（**费用模型实测正确**）；'
    'MAX=20 一直保持；生命 3→2 在采样 55.6s、→1 在 57.3s、判负 ≈63s ⇒ 换算战斗时间 **首漏 ≈44.3s、第二只 ≈46.0s、判负 ≈51.5s**；'
    '③**模拟器同口径 37.3 / 39.8 / 43.7s ⇒ 快约 7s（≈19%）**，这是本轮最重要的保真度发现；'
    '④**已排除**：速度常数（实测 0.414 vs 名义 0.425 格/s，按 moveSpeed 0.85×moveMultiplier 0.5 施加无误）、'
    '斜切拐角（新增 `strict_waypoints` 航点锁定做 A/B：里程 13.38→13.38 格、耗时 37.3→37.3s 无差异，开关默认 False 保留）、'
    '以及 allowDiagonalMove/visitEveryTileCenter（59 条路线全为 True/False）；'
    '⑤**剩余两候选**：(a) 实机路径更长（39.3s×0.425=16.6 格 vs 我们 13.38 格，疑 spawnOffset/出生点门外偏移）；'
    '(b) 实机有效速度更低（13.38/39.3=0.34 格/s，相当于倍率 0.4）；下一步用**逐帧模板匹配跟踪同一只敌人**直接量出格/秒与走线形状定案；'
    '⑥**battle_area 列向标定可信**：两扇蓝门实测在 abs x≈1143/1520，按 pitch_x=130,x0=97 换算正是 col 8/10，与 endPosition (8,8)/(8,10) 吻合；'
    '行向仍受透视压缩，需顶/底分段标定；'
    '⑦**实机 UI 坐标标定**：编队「开始行动」≈(1659,766)、战斗界面干员卡 令≈(1647,985)/蕾缪安≈(1830,985)、'
    '关卡详情「演习」≈(1441,975)、H12-4 节点≈(953,812)——上一轮「点了牌却没部署」是坐标偏了 90px；'
    '⑧**合规**：全程只用演习，理智 111→112 为自然回复（0 消耗），未登录、未触碰禁用界面；'
    '⑨回归全绿：sim 技能 4/4、案例严格模式仍 FAIL@43.7s（待流速修复）；文档 `knowledge/04/41` 新增 §7.49/§7.50。 | 2026-09-14 |'
)

s = io.open(P, encoding='utf-8').read()
anchor = '\n\n## 冲突记录'
if anchor not in s:
    raise SystemExit('anchor not found')
s = s.replace(anchor, ADD + anchor, 1)
io.open(P, 'w', encoding='utf-8', newline='').write(s)
print('T-052 已追加第三十轮；行数 =', len(s.splitlines()))
