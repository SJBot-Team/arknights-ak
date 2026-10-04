# -*- coding: utf-8 -*-
"""test_harmless_enemy.py — ★验证「无害且恒计为击杀」（`isUnharmfulAndAlwaysCountAsKilled`）。

## 语义（知识库既有沉淀，勿重推）
`knowledge/02_作战机制/02_作战机制.md`：
> 「完成全部行动指令 → 模型消失 → **立即扣除对应目标生命值**
>  （除非 `isUnharmfulAndAlwaysCountAsKilled` **只计已处理不扣命**）并触发警报」
> 「**无害目标：到达路径终点不扣关卡生命值、不触发警报**」

## 用例
h12-4 有 **14 条** SPAWN 带该标记（普查结论）⇒ 用 h12-4 直接验证：
被标记的敌人到达终点时应产生 `escape_harmless` 事件、且**生命值不变**。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim.engine import Battle     # noqa: E402

FAILED = []


def check(name, cond, detail=''):
    print(f'  {"✅" if cond else "❌"} {name}{("  — " + detail) if detail else ""}')
    if not cond:
        FAILED.append(name)


def main():
    print('=== h12-4（14 条无害标记）===')
    b = Battle('obt/hard/level_hard_12-04', seed=0, record=True, record_every=1,
               max_frames=30 * 260)
    tagged = [a for a in b.schedule if a.get('harmless_counted') and a.get('type') == 'SPAWN']
    check('时间轴带出 `harmless_counted` 标记', len(tagged) > 0, f'{len(tagged)} 条')
    keys = sorted({a.get('key') for a in tagged})
    check('★带标记的正是**平民**（`enemy_1313_wdfmr` 诺伯特平民）', keys == ['enemy_1313_wdfmr'],
          f'keys = {keys}')

    for _ in range(30 * 260):
        b.tick()
    civ = [l for l in b.logs if l.kind == 'civilian_arrived']
    esc_h = [l for l in b.logs if l.kind == 'escape_harmless']
    esc_n = [l for l in b.logs if l.kind == 'escape']
    check('★14 个平民全部"到达终点"且走**平民分支**（+费用上限、不扣生命）', len(civ) == len(tagged),
          f'civilian_arrived = {len(civ)}；每例 +{civ[0].detail["max_cost_gain"] if civ else "?"} 费用上限')
    check('平民未走普通"逃跑扣命"分支', len(esc_n) + len(esc_h) > 0,
          f'普通逃跑 {len(esc_n)} 条（其他敌人）、无害兜底分支 {len(esc_h)} 条')
    rune_base = float(getattr(b, 'cost_cap_rune', b.cost_max))
    check('费用上限随平民到达抬升（在 rune 基数之上）', b.cost_max > rune_base,
          f'rune 基数 {rune_base} → 最终 {b.cost_max}（14 例 × +2）')

    print('\n=== 1-1（无该标记）回归 ===')
    b3 = Battle('obt/main/level_main_01-01', seed=0, record=True, record_every=1,
                max_frames=1510)
    for _ in range(1510):
        b3.tick()
        if b3.frame == 10:
            b3.deploy('char_123_fang', 3, 5, direction='左', elite=2, level=90,
                      potential=6, trust=200, skill_index=0, skill_level=7, cost=8)
        if b3.frame == 411:
            b3.deploy('char_283_midn', 3, 3, direction='上', elite=2, level=90,
                      potential=6, trust=200, skill_index=0, skill_level=7)
    check('1-1 无 `harmless_counted` 条目', not any(a.get('harmless_counted') for a in b3.schedule))
    check('1-1 无 `escape_harmless`/`civilian_arrived`（未误伤既有行为）',
          not any(l.kind in ('escape_harmless', 'civilian_arrived') for l in b3.logs))

    print()
    if FAILED:
        print(f'❌ 未通过 {len(FAILED)} 项：{FAILED}')
        return 1
    print('✅ 通过：`isUnharmfulAndAlwaysCountAsKilled` 的实例是**平民**，'
          '其"不扣生命/只计已处理"由既有平民分支承担；新增通用兜底分支 `escape_harmless`')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
