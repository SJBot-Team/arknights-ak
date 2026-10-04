# -*- coding: utf-8 -*-
"""check_axis_sp_legality.py — 用「SP 是否足够」判定轴表两种时基哪一种物理可行

背景：轴表多数行没有费用读数，行间时间有两种读法：
  A) cost-relative：费用锚点行 + 其余行按「帧数」列相对上一行推进（我们此前的实现）
  B) abs-seconds ：直接采信表内「绝对时间」列 D + 帧数 C/30

判据：技能只能在其 SP 充满后释放（表值 spData：initSp / spCost / spType / increment）。
      对每个候选时基，逐条检查技能行在**该时基给出的时刻**是否合法；若某时基让大量技能
      行"提前释放"，说明该时基不成立。

另外把「令的天赋：召唤物被撤退/击倒 → +4 SP」计入（h12-4 轴大量撤退召唤物）。
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


def sp_profile(char_id: str, skill_index: int):
    op = get_operator(char_id, elite=2, level=90, potential=6, trust=200, skill_index=skill_index)
    sk = op.get('skill') or {}
    spd = sk.get('spData') or {}
    return {'init': float(spd.get('initSp') or 0.0), 'cost': float(spd.get('spCost') or 0.0),
            'type': spd.get('spType'), 'inc': float(spd.get('increment') or 1.0),
            'name': sk.get('name')}


def check(ax, timebase: str, unit_skill: dict) -> dict:
    """按给定时基算出每条技能行的时刻，检查 SP 合法性。"""
    # 费用记账必须有单位费用表，否则锚点帧全部塌缩（会得到错误的时基结论）
    from ak_sim.data import get_operator as _go
    uc = {}
    for nm in {o.unit for o in ax.ops if o.op == 'deploy'}:
        cid = S.NAME_MAP.get(nm)
        if cid:
            try:
                uc[nm] = int(_go(cid, elite=2, level=90)['attrs'].get('cost') or 0)
            except Exception:
                pass
    plan = ax.resolve_frames(initial_cost=INITIAL, unit_costs=uc, timebase=timebase)
    events = []
    alive = {}          # 名称 → 部署帧
    sp = {}             # 名称 → 当前 SP
    skill_state = {}    # 名称 → 是否激活
    for item, src in zip(plan, ax.ops):
        f = item['frame']
        kind, unit = item['op'], item['unit']
        cid = S.NAME_MAP.get(unit, unit)
        if kind == 'deploy':
            alive[unit] = f
            prof = sp_profile(cid, unit_skill.get(unit, 0))
            sp[unit] = prof['init']
            skill_state[unit] = False
            events.append({'f': f, 'op': 'deploy', 'unit': unit, 'sp': round(sp[unit], 1)})
        elif kind == 'retreat':
            # 召唤物撤退 → 令天赋 +4 SP
            if unit in ('弦惊', '“弦惊”') and '令' in alive:
                sp['令'] = min(sp_profile('char_2023_ling', 2)['cost'], sp.get('令', 0) + 4)
            events.append({'f': f, 'op': 'retreat', 'unit': unit})
            alive.pop(unit, None)
        elif kind == 'skill':
            if unit not in alive:
                events.append({'f': f, 'op': 'skill', 'unit': unit, 'ok': False, 'why': '未部署/已撤退'})
                continue
            prof = sp_profile(cid, unit_skill.get(unit, 0))
            if prof['type'] == 'INCREASE_WITH_TIME':
                cur = min(prof['cost'], sp.get(unit, prof['init'])
                          + prof['inc'] * (f - alive[unit]) / FPS)
            else:
                cur = sp.get(unit, prof['init'])
            ok = cur + 1e-6 >= prof['cost']
            events.append({'f': f, 'op': 'skill', 'unit': unit, 'skill': prof['name'],
                           'have': round(cur, 2), 'need': prof['cost'], 'ok': ok,
                           'early_s': round((prof['cost'] - cur) / max(1e-9, prof['inc']), 2)})
            if ok:
                sp[unit] = 0.0
                alive[unit] = f          # 技能后 SP 从 0 重新计时
    return {'timebase': timebase, 'events': events,
            'skill_total': sum(1 for e in events if e['op'] == 'skill'),
            'skill_ok': sum(1 for e in events if e['op'] == 'skill' and e.get('ok')),
            'skill_illegal': [e for e in events if e['op'] == 'skill' and not e.get('ok')]}


def main():
    ax = parse_cyberplastic(S.XLSM)
    unit_skill = {'蕾缪安': int(sys.argv[1]) if len(sys.argv) > 1 else 2, '令': 2}
    print(f'蕾缪安技能索引 = {unit_skill["蕾缪安"]}（0=重逢问候 1=归乡邀约 2=礼炮·强制追思）')
    for tb in ('cost-relative', 'abs-seconds'):
        r = check(ax, tb, unit_skill)
        print(f'\n=== 时基 {tb} ===')
        print(f'  技能行 {r["skill_total"]} 条，SP 合法 {r["skill_ok"]} 条，'
              f'不合法 {len(r["skill_illegal"])} 条')
        for e in r['events']:
            if e['op'] == 'skill':
                flag = 'OK ' if e.get('ok') else '早 ' + str(e.get('early_s', '')) + 's'
                print(f'    f={e["f"]:>6} ({e["f"]/FPS:>6.1f}s) {e["unit"]:<6} '
                      f'{e.get("skill", e.get("why", "")):<10} SP={e.get("have", "-")}/{e.get("need", "-")} {flag}')
    return 0


if __name__ == '__main__':
    main()
