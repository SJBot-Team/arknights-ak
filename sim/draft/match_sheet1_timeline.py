# -*- coding: utf-8 -*-
"""match_sheet1_timeline.py — 用作者自己记录的时间点（xlsm Sheet1）判定轴表时基

发现：`赛博塑料h12-4.xlsm` 的 **Sheet1** 是作者随手记的**关键事件绝对时刻**（秒），
另有总量行显示整场约 **366 s**。这批数据是**独立于费用读数与绝对时间列**的第三方证据。

做法：把 Sheet1 的标签映射到操作类型（炮=蕾缪安技能、龙=弦惊部署、撤=撤退、令/开令=令相关…），
再对每种候选时间轴求出「最佳匹配后的平均时间偏差」，偏差最小者即最接近作者真实时间轴。

候选时间轴：
  A cost-relative 静态计划      B abs-seconds 静态计划
  C cost-relative + 顺延语义    D abs-seconds + 顺延语义
（顺延语义 = 部署费用不足则顺延、技能 SP 不足则顺延，即脚本实际必须采用的做法）
"""
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
RUN_SECONDS = 366.0            # Sheet1 底部的总时长行
DEFER = {'cost': 0, 'sp': 0, 'frames': 0.0}    # 当前候选时间轴的顺延统计

# Sheet1：标签 → 秒（按时间升序）
SHEET1 = [
    ('5.9过2令', 5.9, '令'),
    ('23.4过2炮', 23.4, 'skill:蕾缪安'),
    ('35.1左上', 35.1, None),
    ('43.8过2撤', 43.8, 'retreat'),
    ('58.3过1炮', 58.3, 'skill:蕾缪安'),
    ('66.1过1下龙', 66.1, 'deploy:弦惊'),
    ('68.0过2开令', 68.0, 'skill:令'),
    ('86.4过2合龙', 86.4, 'deploy:弦惊'),
    ('92.5过2炮', 92.5, 'skill:蕾缪安'),
    ('137.7过1令', 137.7, 'deploy:令'),
    ('138.5过1关', 138.5, None),
    ('140.2炮', 140.2, 'skill:蕾缪安'),
    ('153.3过2合龙', 153.3, 'deploy:弦惊'),
    ('172.6过2开蕾缪安', 172.6, 'skill:蕾缪安'),
]


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


def sp_profile(cid: str, idx: int) -> dict:
    op = get_operator(cid, elite=2, level=90, potential=6, trust=200, skill_index=idx)
    sk = op.get('skill') or {}
    spd = sk.get('spData') or {}
    return {'init': float(spd.get('initSp') or 0.0), 'cost': float(spd.get('spCost') or 0.0),
            'type': spd.get('spType'), 'inc': float(spd.get('increment') or 1.0),
            'bat': float(op['attrs'].get('baseAttackTime') or 1.0)}


def build_timeline(ax, uc, timebase: str, defer: bool, lemuen_skill: int = 2) -> list[dict]:
    """返回 [{frame, op, unit}]：静态计划（defer=False）或按顺延语义推进后的时间轴。

    lemuen_skill：蕾缪安使用的技能索引（0=重逢问候 攻击回复 / 2=礼炮 自动回复）。
    """
    plan = ax.resolve_frames(initial_cost=INITIAL, unit_costs=uc, timebase=timebase)
    out = []
    if not defer:
        for item, o in zip(plan, ax.ops):
            out.append({'frame': float(item['frame']), 'op': o.op, 'unit': o.unit})
        return out
    alive, sp, spc, spt, spi, bat = {}, {}, {}, {}, {}, {}
    spent = 0.0
    cur = 0.0
    for item, o in zip(plan, ax.ops):
        f = max(float(item['frame']), cur)
        kind, unit = o.op, o.unit
        cid = S.NAME_MAP.get(unit, unit)
        reading = INITIAL + f / FPS - spent
        if kind == 'deploy':
            need = uc.get(unit, 0.0)
            if reading + 1e-6 < need:
                d = (need - reading) * FPS
                f += d
                DEFER['cost'] += 1
                DEFER['frames'] += d
                reading = INITIAL + f / FPS - spent
            spent += need
            idx = lemuen_skill if unit == '蕾缪安' else (2 if unit == '令' else 0)
            p = sp_profile(cid, idx)
            alive[unit] = f
            sp[unit], spc[unit], spt[unit], spi[unit] = p['init'], p['cost'], p['type'], p['inc']
            bat[unit] = p['bat']
        elif kind == 'retreat':
            if unit in ('弦惊', '“弦惊”') and '令' in alive:
                sp['令'] = min(spc.get('令', 40.0), sp.get('令', 0.0) + 4.0)
            spent -= uc.get(unit, 0.0) * 0.5
            alive.pop(unit, None)
        elif kind == 'skill' and unit in alive:
            have = sp.get(unit, 0.0)
            t = spt.get(unit)
            if t == 'INCREASE_WITH_TIME':
                have = min(spc[unit], have + spi[unit] * (f - alive[unit]) / FPS)
            elif t == 'INCREASE_WHEN_ATTACK':
                # 攻击回复：按基础攻击间隔折算速率（+increment 每 bat 秒）
                have = min(spc[unit], have + spi[unit] * (f - alive[unit]) / FPS / max(0.1, bat[unit]))
            if have + 1e-6 < spc[unit]:
                d = (spc[unit] - have) / max(1e-9, spi[unit]) * FPS * (
                    max(0.1, bat[unit]) if t == 'INCREASE_WHEN_ATTACK' else 1.0)
                f += d
                DEFER['sp'] += 1
                DEFER['frames'] += d
            sp[unit] = 0.0
            alive[unit] = f
        cur = f
        out.append({'frame': f, 'op': kind, 'unit': unit})
    if out:
        out[0]['defer_stats'] = {'cost': DEFER['cost'], 'sp': DEFER['sp'],
                                 'total_s': round(DEFER['frames'] / FPS, 1)}
    DEFER.update({'cost': 0, 'sp': 0, 'frames': 0.0})
    return out


def match(tl: list[dict], label_type: str | None) -> tuple[float, list]:
    """把每个 Sheet1 事件匹配到**全局最近**的同类操作（允许复用），返回中位偏差与明细。

    不做单调约束：Sheet1 是"关键事件随手记"，与轴表行并非一一对应，
    强行按顺序贪心会在一次错配后把后续全部带偏（这是上一版的缺陷）。
    """
    rows = []
    for label, t, typ in SHEET1:
        best = None
        for it in tl:
            if typ:
                ok = ((typ.startswith('skill:') and it['op'] == 'skill' and it['unit'] == typ.split(':')[1])
                      or (typ.startswith('deploy:') and it['op'] == 'deploy' and it['unit'] == typ.split(':')[1])
                      or (typ == 'retreat' and it['op'] == 'retreat')
                      or (typ == '令' and it['unit'] == '令' and it['op'] == 'deploy'))
                if not ok:
                    continue
            d = abs(it['frame'] / FPS - t)
            if best is None or d < best[0]:
                best = (d, it)
        if best is None:
            rows.append({'label': label, 't': t, 'match': None, 'diff': None})
        else:
            d, it = best
            rows.append({'label': label, 't': t, 'match': f'{it["op"]}:{it["unit"]}',
                         't_match': round(it['frame'] / FPS, 1), 'diff': round(d, 1)})
    diffs = sorted(r['diff'] for r in rows if r['diff'] is not None)
    med = diffs[len(diffs) // 2] if diffs else float('nan')
    return med, rows


def main():
    ax = parse_cyberplastic(S.XLSM)
    uc = unit_costs()
    print(f'Sheet1 事件 {len(SHEET1)} 条；总时长行显示约 {RUN_SECONDS:.0f}s')
    print('（Sheet1 是作者自己记的**绝对时刻**，独立于费用读数与「绝对时间」列）\n')
    results = {}
    variants = [('cost-relative', False, 2), ('abs-seconds', False, 2), ('hybrid', False, 2),
                ('cost-relative', True, 0), ('abs-seconds', True, 0), ('hybrid', True, 0),
                ('cost-relative', True, 2), ('hybrid', True, 2)]
    for tb, defer, lsk in variants:
        tl = build_timeline(ax, uc, tb, defer, lemuen_skill=lsk)
        med, rows = match(tl, None)
        end = tl[-1]['frame'] / FPS
        st = tl[0].get('defer_stats', {'cost': 0, 'sp': 0, 'total_s': 0.0}) if tl else {'cost': 0, 'sp': 0, 'total_s': 0.0}
        name = f'{tb} {"+顺延" if defer else "静态"}' + (f' 蕾S{lsk}' if defer else '')
        results[name] = (med, end, rows)
        print(f'=== {name} ===  匹配中位偏差 {med:.1f}s，轴末尾 {end:.1f}s'
              f'（|末尾−366| = {abs(end - RUN_SECONDS):.1f}s）'
              f'  顺延：费用不足 {st["cost"]} 次 / SP 不足 {st["sp"]} 次 / 合计 {st["total_s"]}s')
        for r in rows:
            if r['diff'] is None:
                print(f'    {r["label"]:<16} 记录 {r["t"]:>6.1f}s  → 无同类操作可匹配')
            else:
                print(f'    {r["label"]:<16} 记录 {r["t"]:>6.1f}s  → {r["t_match"]:>6.1f}s '
                      f'({r["match"]})  Δ={r["diff"]:>5.1f}s')
        print()
    print('=== 排序（匹配中位偏差越小、末尾越接近 366s 越可信）===')
    for name, (med, end, _r) in sorted(results.items(),
                                       key=lambda kv: kv[1][0] + abs(kv[1][1] - RUN_SECONDS) * 0.5):
        print(f'  {name:<26} 中位偏差 {med:>5.1f}s   末尾 {end:>6.1f}s'
              f'（|Δ末尾| = {abs(end - RUN_SECONDS):>5.1f}s）')
    return results


if __name__ == '__main__':
    main()
