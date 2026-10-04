# -*- coding: utf-8 -*-
"""verify_case_timeline.py — 用「费用模型 + 顺延语义」**预测**关键操作时刻，再与作者 Sheet1 对照

核心可检验命题（可离线证伪）：
    在「绝对时间」时基下，弦惊（23 费）按表内时刻排布时费用不足，
    若脚本语义是「不足则顺延到费用足够的那一帧」，则第二批弦惊的落地时刻可**纯解析**算出：
        显示费用(t) = 初始费用 + t − 净消耗  ≥ 23
    把该预测与作者 Sheet1 记录的时刻比对，即可同时检验
    ① 时基（绝对时间列）② 顺延语义 ③ 召唤物扣费 23 ④ 回费速率 1/s。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim import scenario_h124 as S          # noqa: E402
from ak_sim.axis import parse_cyberplastic      # noqa: E402
from ak_sim.data import get_operator            # noqa: E402

FPS = 30
INITIAL = 10.0
REFUND = 0.5

# 作者 Sheet1 中与"召唤物落地/合并"相关的事件
SHEET1_DRAGONS = [('66.1过1下龙', 66.1), ('86.4过2合龙', 86.4), ('153.3过2合龙', 153.3)]

# 作者 Sheet1 全部事件（标签, 秒, 操作类型；None = 不限定类型）
SHEET1_EVENTS = [
    ('5.9过2令', 5.9, ('deploy', '令')),
    ('23.4过2炮', 23.4, ('skill', '蕾缪安')),
    ('35.1左上', 35.1, None),
    ('43.8过2撤', 43.8, ('retreat', None)),
    ('58.3过1炮', 58.3, ('skill', '蕾缪安')),
    ('66.1过1下龙', 66.1, ('deploy', '弦惊')),
    ('68.0过2开令', 68.0, ('skill', '令')),
    ('86.4过2合龙', 86.4, ('deploy', '弦惊')),
    ('92.5过2炮', 92.5, ('skill', '蕾缪安')),
    ('137.7过1令', 137.7, ('deploy', '令')),
    ('138.5过1关', 138.5, None),
    ('140.2炮', 140.2, ('skill', '蕾缪安')),
    ('153.3过2合龙', 153.3, ('deploy', '弦惊')),
    ('172.6过2开蕾缪安', 172.6, ('skill', '蕾缪安')),
]


def _type_ok(item, typ) -> bool:
    if typ is None:
        return True
    op, unit = typ
    return item[0] == op and (unit is None or item[1] == unit)


def unit_costs() -> dict:
    uc = {}
    for nm in ('令', '蕾缪安', '弦惊', '麒麟R夜刀', 'U-Official', '傀影', '艾拉', '雷鸣地雷'):
        cid = S.NAME_MAP.get(nm)
        if cid:
            try:
                uc[nm] = float(get_operator(cid, elite=2, level=90)['attrs'].get('cost') or 0)
            except Exception:
                uc[nm] = 0.0
    return uc


def main():
    ax = parse_cyberplastic(S.XLSM)
    uc = unit_costs()
    plan = ax.resolve_frames(initial_cost=INITIAL, unit_costs=uc, timebase='abs-seconds')

    print('=== 逐条推进（绝对时基 + 不足顺延）===')
    print(f'{"#":>3} {"计划(s)":>8} {"实际操作":<16} {"费用(读)":>8} {"需要":>5} {"实际(s)":>8} {"顺延(s)":>7}')
    spent = 0.0
    cur = 0.0
    predicted_dragons = []
    all_dragons = []
    for n, (item, o) in enumerate(zip(plan, ax.ops)):
        f = max(float(item['frame']), cur)
        reading = INITIAL + f / FPS - spent
        note = ''
        if o.op == 'deploy':
            need = uc.get(o.unit, 0.0)
            if reading + 1e-6 < need:
                wait = (need - reading) * FPS
                f += wait
                reading = INITIAL + f / FPS - spent
                note = f'顺延 {wait/FPS:.1f}s'
            if o.unit == '弦惊':
                all_dragons.append(round(f / FPS, 1))
                if note:
                    predicted_dragons.append(round(f / FPS, 1))
            spent += need
        elif o.op == 'retreat':
            spent -= uc.get(o.unit, 0.0) * REFUND
        cur = f
        print(f'{n+1:>3} {item["frame"]/FPS:>8.1f} {o.op+":"+o.unit:<16} '
              f'{reading:>8.2f} {uc.get(o.unit, 0):>5.0f} {f/FPS:>8.1f} {note:>7}')

    print(f'\n被顺延的弦惊落地时刻：{predicted_dragons}')
    print(f'全部弦惊落地时刻：{all_dragons}')
    print(f'作者 Sheet1 记录的龙相关事件：{[t for _l, t in SHEET1_DRAGONS]}')
    print('\n对照（每个记录事件取最近的预测，Δ 越小越可信）：')
    for label, t in SHEET1_DRAGONS:
        if not all_dragons:
            break
        best = min(all_dragons, key=lambda x: abs(x - t))
        print(f'  {label:<14} 记录 {t:>6.1f}s  ←  预测 {best:>6.1f}s   Δ={abs(best - t):>5.1f}s')

    # ---- 全部 Sheet1 事件 vs 我们推演出的操作时刻（含顺延）----
    print('\n=== 全部 Sheet1 事件对照（类型匹配，取最近）===')
    tl = []
    spent, cur = 0.0, 0.0
    for item, o in zip(plan, ax.ops):
        f = max(float(item['frame']), cur)
        reading = INITIAL + f / FPS - spent
        if o.op == 'deploy':
            need = uc.get(o.unit, 0.0)
            if reading + 1e-6 < need:
                f += (need - reading) * FPS
            spent += need
        elif o.op == 'retreat':
            spent -= uc.get(o.unit, 0.0) * REFUND
        cur = f
        tl.append((o.op, o.unit, f / FPS))
    worst = 0.0
    diffs = []
    for label, t, typ in SHEET1_EVENTS:
        cand = [x for x in tl if _type_ok(x, typ)] or tl
        best = min(cand, key=lambda x: abs(x[2] - t))
        d = abs(best[2] - t)
        worst = max(worst, d)
        diffs.append(d)
        print(f'  {label:<16} 记录 {t:>6.1f}s  ←  {best[0]}:{best[1]:<12} {best[2]:>6.1f}s  Δ={d:>5.1f}s')
    diffs.sort()
    med = diffs[len(diffs) // 2]
    print(f'  最大偏差 {worst:.1f}s，中位偏差 {med:.1f}s（共 {len(diffs)} 条事件）')
    return all_dragons


if __name__ == '__main__':
    main()
