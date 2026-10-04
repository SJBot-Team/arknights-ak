# -*- coding: utf-8 -*-
"""diag_strict.py — 严格模式（判负即停）的真实战果 + 出怪/漏怪时间线。

case_summary 用的是 continue_after_fail=True（对轴模式，会复活战场），
它的「战果/生命」不能当作保真度指标；这里用严格模式看真实结果。
"""
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim import scenario_h124 as S            # noqa: E402
from ak_sim.axis import parse_cyberplastic        # noqa: E402
from ak_sim.engine import Battle                  # noqa: E402

FPS = 30


def main():
    ax = parse_cyberplastic(S.XLSM)
    ops = []
    for o in ax.ops:
        d = o.to_dict()
        d['char'] = S.NAME_MAP.get(o.unit, o.unit)
        for k, v in S.UNIT_CONFIG.get(d['char'], {}).items():
            d.setdefault(k, v)
        ops.append(d)
    plan = ax.resolve_frames(initial_cost=10.0, unit_costs={}, timebase='abs-seconds')
    b = Battle(S.LEVEL, seed=0, record=False)
    b.run_axis(ops, name_map=S.NAME_MAP, coord_transform=S.COORD_TRANSFORM,
               max_frames=30 * 400, continue_after_fail=False,
               retry_on_cost=True, retry_on_sp=False,
               schedule=[int(p['frame']) for p in plan])

    k = Counter(l.kind for l in b.logs)
    print(f'严格模式战果：{b.result}  生命 {b.life}/{b.life_max}  结束帧 {b.frame}'
          f'（{b.frame/FPS:.1f}s）')
    print(f'出怪 {k.get("spawn",0)}  击杀 {k.get("kill",0)}  漏怪 {k.get("escape",0)}  '
          f'平民到达 {k.get("civilian_arrived",0)}  装置摧毁 {k.get("device_destroyed",0)}  '
          f'格挡 {k.get("block",0)}')
    print(f'部署失败 {k.get("deploy_failed",0)}  技能被拒 {k.get("skill_reject",0)}  '
          f'费用上限 {b.cost_max:.0f}')

    print('\n=== 出怪时间线（前 40）===')
    for l in [x for x in b.logs if x.kind == 'spawn'][:40]:
        print(f'  {l.frame:>5}f {l.frame/FPS:6.1f}s  {l.detail.get("enemy")}')

    print('\n=== 漏怪时间线 ===')
    esc = [x for x in b.logs if x.kind == 'escape']
    for l in esc[:40]:
        print(f'  {l.frame:>5}f {l.frame/FPS:6.1f}s  {l.detail.get("enemy")}  生命→{l.detail.get("life")}')
    if len(esc) > 40:
        print(f'  ... 共 {len(esc)} 条')

    print('\n=== 击杀时间线 ===')
    for l in [x for x in b.logs if x.kind == 'kill']:
        print(f'  {l.frame:>5}f {l.frame/FPS:6.1f}s  {l.detail.get("tgt")} ← {l.detail.get("by")}')

    print('\n=== 每秒存活敌人数（每 30 帧采样，前 60s）===')
    # 重新跑一次带采样
    b2 = Battle(S.LEVEL, seed=0, record=False)
    series = []
    orig = Battle.tick

    def tick(self):
        orig(self)
        if self.frame % 30 == 0:
            n = sum(1 for u in self.units.values() if u.side == 'ENEMY' and u.alive)
            series.append((self.frame // 30, n))

    Battle.tick = tick
    b2.run_axis(ops, name_map=S.NAME_MAP, coord_transform=S.COORD_TRANSFORM,
                max_frames=30 * 400, continue_after_fail=False,
                retry_on_cost=True, retry_on_sp=False,
                schedule=[int(p['frame']) for p in plan])
    Battle.tick = orig
    line = ' '.join(f'{s}:{n}' for s, n in series[:60])
    print('  ' + line)
    peak = max(series, key=lambda x: x[1]) if series else (0, 0)
    print(f'  峰值存活 {peak[1]} 只 @ {peak[0]}s')


if __name__ == '__main__':
    main()
