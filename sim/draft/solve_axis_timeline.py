# -*- coding: utf-8 -*-
"""solve_axis_timeline.py — 联合求解轴表「时基 × 费用模型」最自洽组合

问题：赛博塑料 h12-4 轴表 50 条操作里只有 **8 行**带费用读数，其余行没有时间锚点，
于是「行间时间怎么算」有不止一种读法。本脚本用**物理约束**逐一检验候选组合，给出量化结论。

候选维度
  timebase     : cost-relative（费用锚点 + 帧数相对推进） | abs-seconds（表内「绝对时间」列 D + C/30）
  summon_cost  : 弦惊（token_10020_ling_soul3）实际扣费 23 | 0（技能免费召唤）
  refund       : 撤退返还 50% | 0%

三条独立判据（都来自表值/机制，不看"哪种更像人打的"）
  ① 费用读数一致性：在 abs-seconds 下，把 8 个带读数的行放到表内时刻，用费用模型
     `显示费用 = 初始费用 + 时间 − 净消耗` 反算读数，与记录值比较 → Σ|差|
  ② 技能 SP 合法性：技能必须 SP 足够（spData；含令天赋 +4 SP/召唤物损失）→ 非法条数、总提前量
  ③ 部署费用可负担性：部署时显示费用 ≥ 单位费用 → 总顺延帧数（脚本可顺延，但顺延越少越自洽）

输出：各组合的 ①②③ 分数表，分数越低越自洽。
"""
import itertools
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim import scenario_h124 as S          # noqa: E402
from ak_sim.axis import parse_cyberplastic      # noqa: E402
from ak_sim.data import get_operator            # noqa: E402

FPS = 30
INITIAL = 10.0
SUMMON = 'token_10020_ling_soul3'


def unit_costs(summon_cost: float) -> dict:
    uc = {}
    for nm in ('令', '蕾缪安', '弦惊', '麒麟R夜刀', 'U-Official', '傀影', '艾拉', '雷鸣地雷'):
        cid = S.NAME_MAP.get(nm)
        if not cid:
            continue
        try:
            c = int(get_operator(cid, elite=2, level=90)['attrs'].get('cost') or 0)
        except Exception:
            c = 0
        uc[nm] = float(summon_cost) if cid == SUMMON else float(c)
    return uc


def sp_profile(char_id: str, skill_index: int) -> dict:
    op = get_operator(char_id, elite=2, level=90, potential=6, trust=200, skill_index=skill_index)
    sk = op.get('skill') or {}
    spd = sk.get('spData') or {}
    return {'init': float(spd.get('initSp') or 0.0), 'cost': float(spd.get('spCost') or 0.0),
            'type': spd.get('spType'), 'inc': float(spd.get('increment') or 1.0),
            'name': sk.get('name')}


# --------------------------------------------------------------------------------------
# ① 费用读数一致性（仅在 abs-seconds 下可检验：需要"表内时刻"）
# --------------------------------------------------------------------------------------
def test_reading_consistency(ax, uc: dict, refund: float) -> dict:
    rows = []
    spent = 0.0
    worst = 0
    for o in ax.ops:
        t = None
        if o.raw.get('abs_time') is not None:
            t = float(o.raw['abs_time']) + o.foff / FPS
        if o.cost is not None and t is not None:
            model = INITIAL + t - spent
            diff = model - float(o.cost)
            rows.append({'t': round(t, 2), 'recorded': o.cost, 'model': round(model, 2),
                         'diff': round(diff, 2), 'kind': o.op, 'unit': o.unit})
            worst = max(worst, abs(diff))
        # 记账（用**表内顺序**推进）
        nm = o.unit
        if o.op == 'deploy':
            spent += uc.get(nm, 0.0)
        elif o.op == 'retreat':
            spent -= uc.get(nm, 0.0) * refund
    return {'rows': rows, 'sum_abs': round(sum(abs(r['diff']) for r in rows), 2),
            'max_abs': round(worst, 2), 'mean_abs': round(
                sum(abs(r['diff']) for r in rows) / max(1, len(rows)), 2)}


# --------------------------------------------------------------------------------------
# ② 技能 SP 合法性 + ③ 部署可负担性（两种时基都能算）
# --------------------------------------------------------------------------------------
def simulate(ax, timebase: str, uc: dict, refund: float) -> dict:
    plan = ax.resolve_frames(initial_cost=INITIAL, unit_costs=uc, refund_ratio=refund,
                             timebase=timebase)
    alive, sp, sp_cost, sp_type, sp_inc = {}, {}, {}, {}, {}
    skill_unit_costs = {'蕾缪安': 2, '令': 2}       # 案例配装：两人都按 3 技能
    spent = 0.0
    cur = 0.0
    sp_illegal, sp_early_total = 0, 0.0
    sp_not_alive = 0
    deploy_delay_total = 0.0
    deploy_unaffordable = 0
    cur_frame = 0.0
    trace = []
    for item, o in zip(plan, ax.ops):
        f = max(float(item['frame']), cur_frame)     # 顺序语义：不得早于上一条
        kind, unit = o.op, o.unit
        cid = S.NAME_MAP.get(unit, unit)
        reading = INITIAL + f / FPS - spent
        if kind == 'deploy':
            need = uc.get(unit, 0.0)
            if reading + 1e-6 < need:                # 费用不足 → 顺延到可负担
                wait = (need - reading) * FPS
                deploy_delay_total += wait
                deploy_unaffordable += 1
                trace.append({'f': round(f), 'unit': unit, 'why': 'deploy_cost',
                              'have': round(reading, 2), 'need': need, 'wait_s': round(wait / FPS, 1)})
                f += wait
                reading = INITIAL + f / FPS - spent
            spent += need
            idx = skill_unit_costs.get(unit, 0)
            p = sp_profile(cid, idx)
            alive[unit] = f
            sp[unit] = p['init']
            sp_cost[unit] = p['cost']
            sp_type[unit] = p['type']
            sp_inc[unit] = p['inc']
        elif kind == 'retreat':
            if unit in ('弦惊', '“弦惊”') and '令' in alive:
                sp['令'] = min(sp_cost.get('令', 40.0), sp.get('令', 0.0) + 4.0)
            spent -= uc.get(unit, 0.0) * refund
            alive.pop(unit, None)
        elif kind == 'skill':
            if unit not in alive:
                sp_illegal += 1
                sp_not_alive += 1
                trace.append({'f': round(f), 'unit': unit, 'why': 'not_alive'})
                cur_frame = f
                continue
            if sp_type.get(unit) == 'INCREASE_WITH_TIME':
                have = min(sp_cost[unit], sp.get(unit, 0.0) + sp_inc[unit] * (f - alive[unit]) / FPS)
            else:
                have = sp.get(unit, 0.0)
            if have + 1e-6 < sp_cost[unit]:
                sp_illegal += 1
                early = (sp_cost[unit] - have) / max(1e-9, sp_inc[unit])
                sp_early_total += early
                trace.append({'f': round(f), 'unit': unit, 'why': 'sp', 'have': round(have, 1),
                              'need': sp_cost[unit], 'early_s': round(early, 1)})
                f += early * FPS                      # 顺延到可释放
                have = sp_cost[unit]
            sp[unit] = 0.0
            alive[unit] = f                           # 技能期不回复（近似）
        cur_frame = f
    return {'timebase': timebase, 'sp_illegal': sp_illegal, 'sp_not_alive': sp_not_alive,
            'sp_early_total_s': round(sp_early_total, 1), 'trace': trace,
            'deploy_unaffordable': deploy_unaffordable,
            'deploy_delay_s': round(deploy_delay_total / FPS, 1),
            'end_frame': int(cur_frame), 'end_s': round(cur_frame / FPS, 1)}


def main():
    ax = parse_cyberplastic(S.XLSM)
    print(f'轴表 {len(ax.ops)} 条；带费用读数 {sum(1 for o in ax.ops if o.cost is not None)} 条\n')

    print('=== 判据① 费用读数一致性（abs-seconds 下表内时刻 vs 费用模型）===')
    best1 = None
    for summon_cost, refund in itertools.product((23.0, 0.0), (0.5, 0.0)):
        r = test_reading_consistency(ax, unit_costs(summon_cost), refund)
        tag = f'召唤物={summon_cost:>4.0f} 返还={refund:.1f}'
        print(f'  {tag}  Σ|差|={r["sum_abs"]:>7.2f}  平均={r["mean_abs"]:>6.2f}  最大={r["max_abs"]:>6.2f}')
        if best1 is None or r['sum_abs'] < best1[0]:
            best1 = (r['sum_abs'], tag, r)
    print(f'  → 最自洽：{best1[1]}（Σ|差|={best1[0]:.2f}）')
    for row in best1[2]['rows']:
        print(f'      t={row["t"]:>7.2f}s 记录={row["recorded"]:>3} 模型={row["model"]:>7.2f} '
              f'差={row["diff"]:>6.2f}  {row["kind"]} {row["unit"]}')

    print('\n=== 判据②③ 技能 SP 合法性 / 部署费用可负担性 ===')
    print(f'{"时基":<14} {"召唤物":>5} {"返还":>4} {"SP非法":>6} {"未在场":>6} {"SP提前(s)":>9} '
          f'{"部署不足":>7} {"顺延(s)":>7} {"末尾(s)":>7}')
    results = []
    for tb, summon_cost, refund in itertools.product(
            ('cost-relative', 'abs-seconds'), (23.0, 0.0), (0.5, 0.0)):
        r = simulate(ax, tb, unit_costs(summon_cost), refund)
        results.append((tb, summon_cost, refund, r))
        print(f'{tb:<14} {summon_cost:>5.0f} {refund:>4.1f} {r["sp_illegal"]:>6} '
              f'{r["sp_not_alive"]:>6} {r["sp_early_total_s"]:>9.1f} {r["deploy_unaffordable"]:>7} '
              f'{r["deploy_delay_s"]:>7.1f} {r["end_s"]:>7.1f}')
    print('\n  仅「SP 不足」类不合法（排除"该干员已撤退/未部署"）的对比：')
    for tb, summon_cost, refund, r in results:
        short = [t for t in r['trace'] if t['why'] == 'sp']
        if summon_cost == 23.0 and refund == 0.5:
            print(f'    {tb:<14} SP 不足 {len(short)} 条，提前量合计 {r["sp_early_total_s"]}s')
            for t in short[:8]:
                print(f'        f={t["f"]:>6} {t["unit"]:<6} SP={t["have"]}/{t["need"]} 早 {t["early_s"]}s')
            dep = [t for t in r['trace'] if t['why'] == 'deploy_cost']
            print(f'    部署费用不足 {len(dep)} 次：')
            for t in dep[:8]:
                print(f'        f={t["f"]:>6} {t["unit"]:<6} 费用={t["have"]}/{t["need"]} 顺延 {t["wait_s"]}s')

    # 综合评分：SP 非法条数 + 部署顺延（归一到秒）+ 读数一致性（仅 abs 有意义）
    print('\n=== 综合（分数越低越自洽）===')
    for tb, summon_cost, refund, r in sorted(
            results, key=lambda x: (x[3]['sp_illegal'], x[3]['deploy_delay_s'])):
        score = r['sp_illegal'] * 100 + r['deploy_delay_s'] * 0.5
        print(f'  {tb:<14} 召唤物={summon_cost:>4.0f} 返还={refund:.1f}  '
              f'综合分={score:>7.1f}  （SP非法 {r["sp_illegal"]} 条 + 部署顺延 {r["deploy_delay_s"]}s）')
    return results


if __name__ == '__main__':
    main()
