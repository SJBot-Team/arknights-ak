# -*- coding: utf-8 -*-
"""diag_lemuen_target.py — 蕾缪安在场期间：射程内敌人数、当前目标、对装置命中、以及「空档」帧数。

问题（§7.51 遗留）：作者作战记录第 7 行在 29.0s（按键意图）就安排第一条弦惊，
而弦惊 23 费 > 上限 20 ⇒ 上限必须先抬升。抬升只能靠「拆掉应急储备 +5」或「平民到达 +2」。
蕾缪安是唯一覆盖储备 (5,6)/(5,7) 的单位，所以她能不能把储备打完是关键。
本脚本量化：她的射程里到底有没有「没有敌人」的空档 —— 有 = 应该能打储备（说明索敌/转火有 bug），
没有 = 储备在纯索敌规则下永远打不掉（说明作者的实机里另有机制或工具在重试等待）。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim import scenario_h124 as S               # noqa: E402
from ak_sim.axis import parse_cyberplastic           # noqa: E402
from ak_sim.engine import Battle                     # noqa: E402

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

    stats = {'frames': 0, 'with_enemy': 0, 'device_target': 0, 'enemy_target': 0, 'idle': 0}
    dev_hits = []
    lem_uid = [None]
    orig_tick = Battle.tick

    def tk(self):
        orig_tick(self)
        uid = lem_uid[0]
        u = self.units.get(uid) if uid else None
        if u is None or not u.alive or u.side != 'ALLY':
            for cand in self.units.values():
                if cand.side == 'ALLY' and cand.name == '蕾缪安':
                    lem_uid[0] = cand.uid
            return
        stats['frames'] += 1
        ens = self.enemies_in_range(u)
        if ens:
            stats['with_enemy'] += 1
        else:
            stats['idle'] += 1
        tgt = self.pick_operator_target(u)
        if tgt is not None:
            if tgt.side == 'DEVICE':
                stats['device_target'] += 1
            else:
                stats['enemy_target'] += 1
        for l in self.logs[-6:]:
            if l.kind == 'hit' and l.detail.get('src') == '蕾缪安' and \
                    str(l.detail.get('tgt', '')).startswith('街头'):
                dev_hits.append((l.frame, l.detail))

    Battle.tick = tk
    b.run_axis(ops, name_map=S.NAME_MAP, coord_transform=S.COORD_TRANSFORM,
               max_frames=30 * 400, continue_after_fail=True,
               retry_on_cost=True, retry_on_sp=False,
               schedule=[int(p['frame']) for p in plan])
    Battle.tick = orig_tick

    print('蕾缪安在场帧统计：')
    print(f"  在场 {stats['frames']} 帧（{stats['frames']/FPS:.0f}s）")
    print(f"  射程内有敌人 {stats['with_enemy']} 帧（{100*stats['with_enemy']/max(1,stats['frames']):.1f}%）")
    print(f"  射程内无敌人（空档）{stats['idle']} 帧（{stats['idle']/FPS:.1f}s）")
    print(f"  目标=敌人 {stats['enemy_target']} 帧 / 目标=装置 {stats['device_target']} 帧")
    print(f'\n对「街头应急储备」的命中 {len(dev_hits)} 次：')
    for f, d in dev_hits:
        print(f'  {f:>5}f {f/FPS:6.1f}s dmg={d.get("dmg")} hp_after={d.get("hp_after")}')
    b2 = Battle(S.LEVEL, seed=0, record=False)
    print(f'\n装置事件：', [l.detail for l in b.logs if l.kind in ('device_killed', 'device_destroyed')])
    print(f'最终上限 {b.cost_max:.0f}')


if __name__ == '__main__':
    main()
