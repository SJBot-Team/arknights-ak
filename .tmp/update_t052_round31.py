# -*- coding: utf-8 -*-
"""update_t052_round31.py — 写入 T-052 第三十一轮（检查点被跳过 → 流速修复，实机验证收敛）。"""
import io
import sys

sys.stdout.reconfigure(encoding='utf-8')

P = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
ADD = (
    ' **第三十一轮（★根因已修复并实机验证：检查点被整段跳过）**：'
    '①**根因**：`battlemap.build_routes()` 把检查点的 `position` 写成了**裸 row 整数**，'
    '而 `engine._process_checkpoints()` 只认 `position` 字典 ⇒ `isinstance` 判定失败后每个 MOVE 检查点都在同一帧被"瞬间完成"，'
    '敌人绕过全部检查点直奔 route_end；'
    '②**证伪链**：`diag_flow_speed.py` 里程计显示路线0 实际只走 13.38 格，而检查点折线是 16.00 格；'
    '`CHECKPOINT_ARRIVE_PAD` 0.5→0 完全无影响（因为检查点根本没生效）——这正是上一轮"宽容度不影响路径"反常现象的来源；'
    '修复后 A/B 立刻单调：PAD 0.5/0.25/0.05/0.0 → 里程 14.02/14.48/15.13/15.35 格、首漏 38.4/39.6/41.4/42.0s；'
    '③**实机验证收敛**：实机首漏 44.3s、第二只 46.0s、判负 ≈51.5s；模拟器修复前 37.3/39.8/43.7，'
    '**修复后 42.0/44.5/51.5 —— 判负时刻完全一致，三条时间线全部进 ±2s**；'
    '④PAD 取值有了数据依据：关卡每个检查点 `reachDistance=0.0`/`reachOffset=(0,0)`（=必须走到点上），故取 0；'
    '⑤**连带语义修正**：轴操作可重试原因扩为 `cost/occupied/tile`（打图端是"按到成功为止"；实测出现过「弦惊 D11 被路过敌人占格而失败」），'
    '但 `sp` 仍受 `retry_on_sp` 控制（第一次改表把 sp 放进常驻重试集合导致 skill_reject 3→438，已修正）；'
    '⑥**指标口径修正**：`case_summary` 的"弦惊落地"原先把失败尝试算作落地（36.3s 那次是 `occupied` 失败），'
    '现在只计 `ok=True` 并单列失败尝试 ⇒ 真实落地 55.8/77.0/102.2s（作者作战记录第 7 行写 29.0s）；'
    '⑦**剩余明确目标**：上限 20 放不下 23 费的弦惊，必须靠"拆储备 +5 / 平民 +2"抬升；修复流速后蕾缪安对储备命中 1→2 次'
    '（20.0/22.8s，各 1367，储备 8000 HP），但敌人一进射程就转火 ⇒ 储备始终没被拆掉，上限只能靠平民（首个 ≈45s 到达）慢慢涨到 22；'
    '下一步攻"让蕾缪安把储备打完"（索敌优先级 / 靠弦惊与令形成空档）；'
    '⑧回归全绿：sim 技能 4/4、案例顺延 PASS、严格模式仍 FAIL@51.5s（=实机同刻，属于"计划本身打不过"而非流速问题）；'
    '文档 `knowledge/04/41` 新增 §7.51/§7.52。 | 2026-09-14 |'
)

s = io.open(P, encoding='utf-8').read()
anchor = '\n\n## 冲突记录'
if anchor not in s:
    raise SystemExit('anchor not found')
s = s.replace(anchor, ADD + anchor, 1)
io.open(P, 'w', encoding='utf-8', newline='').write(s)
print('T-052 已追加第三十一轮；行数 =', len(s.splitlines()))
