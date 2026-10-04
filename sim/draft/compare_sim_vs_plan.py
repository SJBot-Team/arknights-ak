# -*- coding: utf-8 -*-
"""compare_sim_vs_plan.py — 轴表「静态帧计划」与「模拟动态执行」逐条比对

两种时基都算一遍：
  * cost-relative（默认）：费用读数锚点 + 帧数相对推进（PRTS+ 使用须知第三条：费用与费用条是唯一时间参照）
  * abs-seconds        ：直接采信表内「绝对时间」列（D + C/30）

用途：定位执行端时序语义与静态换算的偏差来源（费用读数、消耗记账、±1 帧语义）。

用法：
    cd ak/sim/draft
    <venv>/python.exe -X utf8 compare_sim_vs_plan.py [--limit 20]
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim import scenario_h124 as S          # noqa: E402
from ak_sim.axis import parse_cyberplastic      # noqa: E402
from ak_sim.data import get_operator            # noqa: E402

INITIAL = 10.0        # h12-4 关卡初始费用


def unit_costs(ax) -> dict:
    out = {}
    for nm in {o.unit for o in ax.ops if o.op == 'deploy'}:
        cid = S.NAME_MAP.get(nm)
        if not cid:
            continue
        try:
            out[nm] = int(get_operator(cid, elite=2, level=90)['attrs'].get('cost') or 0)
        except Exception:
            out[nm] = 0
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=20)
    args = ap.parse_args()

    ax = parse_cyberplastic(S.XLSM)
    uc = unit_costs(ax)
    b, fired = S.main()
    plan_c = ax.resolve_frames(initial_cost=INITIAL, unit_costs=uc, timebase='cost-relative')
    plan_a = ax.resolve_frames(initial_cost=INITIAL, unit_costs=uc, timebase='abs-seconds')

    print(f'\n部署费用表（满配）: {uc}')
    print('\n=== 静态计划(cost-relative) vs 静态计划(abs-seconds) vs 模拟动态执行 ===')
    print(f'{"#":>3} {"操作":<7} {"单位":<16} {"动态帧":>7} {"锚点帧":>7} {"Δ锚":>5} '
          f'{"绝对秒帧":>8} {"Δ绝":>6} {"费用锚":>6} {"实读":>5} {"净消耗":>7} {"结果":<5}')
    for i, f in enumerate(fired[:args.limit]):
        if i >= len(plan_c):
            break
        print(f'{i+1:>3} {f["op"]:<7} {f["unit"]:<16} {f["frame"]:>7} {plan_c[i]["frame"]:>7} '
              f'{f["frame"] - plan_c[i]["frame"]:>5} {plan_a[i]["frame"]:>8} '
              f'{f["frame"] - plan_a[i]["frame"]:>6} {str(f.get("cost_ref")):>6} '
              f'{str(f.get("cost_at")):>5} {plan_c[i]["spent_before"]:>7} '
              f'{"OK" if f.get("ok") else "FAIL":<5}')

    for tag, plan in (('cost-relative', plan_c), ('abs-seconds', plan_a)):
        diffs = [f['frame'] - plan[i]['frame'] for i, f in enumerate(fired) if i < len(plan)]
        exact = sum(1 for d in diffs if d == 0)
        near = sum(1 for d in diffs if abs(d) <= 2)
        print(f'\n[{tag}] 完全一致 {exact}/{len(diffs)}，±2 帧内 {near}，'
              f'最大帧差 {max((abs(d) for d in diffs), default=0)}')

    # 费用读数自检：模拟执行时实读费用 vs 轴表锚点（两者一致说明消耗记账模型正确）
    print('\n=== 费用锚点自检（模拟实读 vs 轴表记录）===')
    bad = 0
    for i, f in enumerate(fired):
        ref = f.get('cost_ref')
        got = f.get('cost_at')
        if ref is None:
            continue
        flag = 'OK' if got == ref else 'MISMATCH'
        if got != ref:
            bad += 1
        print(f'  第 {i+1:>2} 条 {f["op"]:<7} {f["unit"]:<16} 锚点={ref:<3} 实读={got:<3} '
              f'模拟帧={f["frame"]:<5} {flag}')
    print(f'  锚点不一致 {bad} 处')
    return fired, plan_c, plan_a


if __name__ == '__main__':
    main()
