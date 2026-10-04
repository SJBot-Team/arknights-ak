# -*- coding: utf-8 -*-
"""dp_ledger.py — 在**正确费用上限模型**下跑轴表，输出逐条 DP 账本并与作者时间线对照

正确模型（实机 + 关卡数据得出，见 knowledge/04/41 §7.24/§7.26/§7.28）：
  * runes `cbuff_max_cost` 把费用上限压到 **20**（天花板 99）；
  * 2 个「街头应急储备」(5,6)/(5,7) 被**敌人**摧毁后各 +5 上限与 +5 费用（实测 22.3s/25.3s）。
执行语义：部署费用不足 → 顺延；技能 SP 不足 → **按脚本行为"点了没反应"直接跳过**（不阻塞），
          这由 `retry_on_sp=False` 控制。

输出：每条操作的 计划帧 / 实际帧 / 触发前 DP / 消耗 / 是否顺延，以及弦惊落地时刻与作者 Sheet1 对照。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim import scenario_h124 as S          # noqa: E402
from ak_sim.axis import parse_cyberplastic      # noqa: E402
from ak_sim.data import get_operator            # noqa: E402
from ak_sim.engine import Battle                # noqa: E402

FPS = 30
INITIAL = 10.0
SHEET1_DRAGONS = [66.1, 86.4, 153.3]


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
    ops = []
    for o in ax.ops:
        d = o.to_dict()
        d['char'] = S.NAME_MAP.get(o.unit, o.unit)
        for k, v in S.UNIT_CONFIG.get(d['char'], {}).items():
            d.setdefault(k, v)
        ops.append(d)
    plan = ax.resolve_frames(initial_cost=INITIAL, unit_costs=uc, timebase='abs-seconds')
    sched = [int(p['frame']) for p in plan]

    b = Battle(S.LEVEL, seed=0, record=False)
    print(f'费用上限（rune 后）= {b.cost_max}（天花板 {b.cost_cap_ceil}）；场上装置：'
          f'{[u.name for u in b.units.values() if u.side == "DEVICE"]}')
    fired = b.run_axis(ops, name_map=S.NAME_MAP, coord_transform=S.COORD_TRANSFORM,
                       max_frames=30 * 400, continue_after_fail=True,
                       retry_on_cost=True, retry_on_sp=False, schedule=sched)

    print(f'\n{"#":>3} {"计划s":>7} {"实际s":>7} {"顺延s":>6} {"DP前":>6} {"费用":>4} '
          f'{"操作":<7} {"单位":<10} {"结果"}')
    for i, r in enumerate(fired):
        disc = next((l for l in b.logs if l.frame == r['frame'] and l.kind == 'deploy'
                     and l.detail.get('char') == S.NAME_MAP.get(r['unit'], r['unit'])), None)
        dp_before = ''
        if disc:
            try:
                dp_before = round(float(disc.detail.get('cost', 0)), 0)
            except Exception:
                dp_before = ''
        print(f'{i+1:>3} {plan[i]["frame"]/FPS:>7.1f} {r["frame"]/FPS:>7.1f} '
              f'{r.get("wait_frames", 0)/FPS:>6.1f} {str(dp_before):>6} '
              f'{uc.get(r["unit"], 0):>4.0f} {r["op"]:<7} {r["unit"][:10]:<10} '
              f'{"OK" if r.get("ok") else r.get("reason", "FAIL")}')

    drag = [round(x['frame'] / FPS, 1) for x in fired
            if x['op'] == 'deploy' and x['unit'] == 'token_10020_ling_soul3']
    print(f'\n弦惊落地：{drag[:6]}')
    print(f'作者 Sheet1：{SHEET1_DRAGONS}')
    dev = [(l.frame, round(l.frame/FPS, 1), l.detail.get('cost_max')) for l in b.logs
           if l.kind == 'device_destroyed']
    print(f'储备被摧毁：{dev}')
    print(f'结束时：费用上限 {b.cost_max}，DP {round(b.cost,1)}，帧 {b.frame}')


if __name__ == '__main__':
    main()
