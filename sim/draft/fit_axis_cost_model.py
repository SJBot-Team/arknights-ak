# -*- coding: utf-8 -*-
"""fit_axis_cost_model.py — 用轴表 8 个费用读数**反解**作者的消耗记账模型

轴表 8 行带费用读数（其余行为空）。若「绝对时间」列 D 是作者记录的真实时刻，
则每条读数满足：显示费用 = 初始费用 + 时间 − 净消耗。
净消耗 = Σ部署费用 − 返还率×Σ撤退费用。

未知量：①召唤物（弦惊）的实际扣费 c；②作者的返还率 ρ（可能压根没算）。
本脚本在 (c, ρ) 网格上最小化 Σ(模型读数 − 记录读数)²，给出最优解与残差，
从而判断「召唤物费用」与「返还是否被计入」这两件一直悬着的事。
"""
import itertools
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim import scenario_h124 as S          # noqa: E402
from ak_sim.axis import parse_cyberplastic      # noqa: E402
from ak_sim.data import get_operator            # noqa: E402

FPS = 30
INITIAL = 10.0
SUMMON_CIDS = ('token_10020_ling_soul3', 'token_10033_ela_grzmot')


def base_costs() -> dict:
    uc = {}
    for nm, cid in S.NAME_MAP.items():
        if not cid.startswith(('char_', 'token_')):
            continue
        try:
            uc[nm] = float(get_operator(cid, elite=2, level=90)['attrs'].get('cost') or 0)
        except Exception:
            pass
    return uc


def residual(ax, uc_base: dict, summon_cost: float, refund: float, rows_out=None):
    spent = 0.0
    se = 0.0
    n = 0
    out = []
    for o in ax.ops:
        t = o.raw.get('abs_time')
        if o.cost is not None and t is not None:
            tt = float(t) + o.foff / FPS
            model = INITIAL + tt - spent
            d = model - float(o.cost)
            se += d * d
            n += 1
            out.append((round(tt, 2), o.cost, round(model, 2), round(d, 2), o.op, o.unit))
        nm = o.unit
        cid = S.NAME_MAP.get(nm, '')
        c = summon_cost if cid in SUMMON_CIDS else uc_base.get(nm, 0.0)
        if o.op == 'deploy':
            spent += c
        elif o.op == 'retreat':
            spent -= c * refund
    if rows_out is not None:
        rows_out.extend(out)
    return se, n


def main():
    ax = parse_cyberplastic(S.XLSM)
    base = base_costs()
    print('非召唤物单位费用表（满配）:', {k: base.get(k) for k in
                                 ('令', '蕾缪安', '麒麟R夜刀', 'U-Official', '傀影', '艾拉')})
    print(f'\n带读数的行：{sum(1 for o in ax.ops if o.cost is not None)} 条\n')

    best = None
    print(f'{"召唤物费":>8} {"返还率":>6} {"RMSE":>8}')
    for summon_cost in range(0, 31):
        for refund in (0.0, 0.25, 0.5, 0.75, 1.0):
            se, n = residual(ax, base, float(summon_cost), refund)
            rmse = math.sqrt(se / max(1, n))
            print(f'{summon_cost:>8} {refund:>6.2f} {rmse:>8.2f}')
            if best is None or rmse < best[0]:
                best = (rmse, summon_cost, refund)
    print(f'\n最优：召唤物扣费 = {best[1]} DP，返还率 = {best[2]:.2f}，RMSE = {best[0]:.2f}')
    rows = []
    residual(ax, base, float(best[1]), best[2], rows)
    print('\n各读数行的残差（模型 − 记录）：')
    print(f'{"时刻(s)":>8} {"记录":>5} {"模型":>7} {"残差":>7}  操作')
    for tt, rec, model, d, op, unit in rows:
        print(f'{tt:>8.2f} {rec:>5} {model:>7.2f} {d:>7.2f}  {op} {unit}')

    # 参照：官方表值 23 + 常见返还 50%
    se, n = residual(ax, base, 23.0, 0.5)
    print(f'\n参照（表值 23 DP + 返还 50%）：RMSE = {math.sqrt(se/n):.2f}')
    se, n = residual(ax, base, 23.0, 0.0)
    print(f'参照（表值 23 DP + 不计返还）：RMSE = {math.sqrt(se/n):.2f}')


if __name__ == '__main__':
    main()
