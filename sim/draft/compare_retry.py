# -*- coding: utf-8 -*-
"""compare_retry.py — 「费用不足顺延重试」执行语义的效果对比 + 帧记录导出

对比同一轴表在 retry_on_cost=False / True 下的：
  * 触发与成功条数
  * 与静态帧计划的吻合度（±2 帧内条数）
  * 最终战果（WIN/FAIL、生命、漏怪）

并把两次运行的逐条触发帧导出为 JSON（`data/derived/sim_axis_frames_retry.json`），
供打图端（`code/vision/apps/test_ruler_clock.py` 段 E）做**两端时序交叉验证**。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim import scenario_h124 as S          # noqa: E402
from ak_sim.axis import parse_cyberplastic      # noqa: E402
from ak_sim.data import get_operator            # noqa: E402
from ak_sim.engine import Battle                # noqa: E402

INITIAL = 10.0


def build_ops(ax):
    ops = []
    for o in ax.ops:
        d = o.to_dict()
        d['char'] = S.NAME_MAP.get(o.unit, o.unit)
        for k, v in S.UNIT_CONFIG.get(d['char'], {}).items():
            d.setdefault(k, v)
        ops.append(d)
    return ops


def main():
    ax = parse_cyberplastic(S.XLSM)
    uc = {}
    for nm in {o.unit for o in ax.ops if o.op == 'deploy'}:
        cid = S.NAME_MAP.get(nm)
        if cid:
            try:
                uc[nm] = int(get_operator(cid, elite=2, level=90)['attrs'].get('cost') or 0)
            except Exception:
                pass
    plan = ax.resolve_frames(initial_cost=INITIAL, unit_costs=uc)
    # 绝对时基计划（离线证据判定：表内「绝对时间」列更接近作者真实时间轴，见 knowledge/04/41 §7.12）
    plan_abs = ax.resolve_frames(initial_cost=INITIAL, unit_costs=uc, timebase='abs-seconds')
    sched_abs = [int(p['frame']) for p in plan_abs]
    ops = build_ops(ax)

    dump_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                            '..', '..', 'data', 'derived'))
    dump = {'level': S.LEVEL, 'initial_cost': INITIAL, 'unit_costs': uc,
            'timebase': 'abs-seconds', 'source': 'compare_retry.py'}
    for retry in (False, True):
        b = Battle(S.LEVEL, seed=0)
        # 两端时序交叉验证要**隔离变量**：只比较「费用/调度」语义，故关闭技能 SP 门槛
        # （开启 SP 门槛后的差异见 compare_retry 的 sp_gated 统计与 check_axis_sp_legality.py）
        b.skill_gate = False
        fired = b.run_axis(ops, name_map=S.NAME_MAP, coord_transform=S.COORD_TRANSFORM,
                           max_frames=30 * 400, continue_after_fail=True, retry_on_cost=retry,
                           schedule=sched_abs)
        diffs = [x['frame'] - plan_abs[i]['frame'] for i, x in enumerate(fired) if i < len(plan_abs)]
        print(f'\n--- retry_on_cost={retry} ---')
        print(f'  触发 {len(fired)}/{len(ops)}，成功 {sum(1 for x in fired if x.get("ok"))}，'
              f'重试 {len(getattr(b, "axis_retries", []))} 次')
        print(f'  战果 {b.result} 生命 {b.life} 帧 {b.frame}（{b.frame/30:.1f}s）')
        print(f'  与计划：完全一致 {sum(1 for d in diffs if d == 0)}，±2 帧内 {sum(1 for d in diffs if abs(d) <= 2)}，'
              f'最大帧差 {max((abs(d) for d in diffs), default=0)}')
        print(f'  前 12 条帧差: {diffs[:12]}')
        fails = [(i + 1, x['op'], x['unit'], x.get('reason'), x.get('need'), x.get('have'))
                 for i, x in enumerate(fired) if not x.get('ok')]
        print(f'  失败操作 {len(fails)}: {fails[:8]}')
        key = 'retry' if retry else 'no_retry'
        dump['schedule_' + key] = [int(x['frame']) for x in plan_abs]
        dump[key] = [{'idx': i, 'op': x['op'], 'unit': x['unit'], 'frame': x['frame'],
                      'cost_at': x.get('cost_at'), 'cost_ref': x.get('cost_ref'),
                      'wait_frames': x.get('wait_frames'), 'ok': bool(x.get('ok')),
                      'reason': x.get('reason'), 'need': x.get('need'), 'have': x.get('have')}
                     for i, x in enumerate(fired)]
        dump['result_' + key] = {'result': b.result, 'life': b.life, 'frames': b.frame,
                                 'success': sum(1 for x in fired if x.get('ok'))}

    out = os.path.join(dump_dir, 'sim_axis_frames_retry.json')
    os.makedirs(dump_dir, exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(dump, f, ensure_ascii=False, indent=1)
    print(f'\n模拟侧帧记录 → {out}')

    # 额外：开启技能 SP 门槛后的对照（体现"轴表时基是否物理可行"）
    b2 = Battle(S.LEVEL, seed=0)          # skill_gate 默认 True
    b2.sp_assume_attacking = True         # 与打图端同一假设（攻击回复按理想速率）
    fired2 = b2.run_axis(ops, name_map=S.NAME_MAP, coord_transform=S.COORD_TRANSFORM,
                         max_frames=30 * 400, continue_after_fail=True, retry_on_cost=True,
                         schedule=sched_abs)
    sp_rej = sum(1 for x in fired2 if x.get('reason') == 'sp')
    print(f'\n[对照] 开启技能 SP 门槛：触发 {len(fired2)}/{len(ops)}，其中因 SP 不足被拒 {sp_rej} 次；'
          f'战果 {b2.result} 生命 {b2.life}')
    dump['retry_spgate'] = [{'idx': i, 'op': x['op'], 'unit': x['unit'], 'frame': x['frame'],
                             'cost_at': x.get('cost_at'), 'reason': x.get('reason'),
                             'ok': bool(x.get('ok'))} for i, x in enumerate(fired2)]
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(dump, f, ensure_ascii=False, indent=1)
    return dump


if __name__ == '__main__':
    main()
