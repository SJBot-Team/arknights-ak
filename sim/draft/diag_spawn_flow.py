# -*- coding: utf-8 -*-
"""diag_spawn_flow.py — 出怪时间线 × 路线首检查点 × 实际穿行耗时（核对是否重复计时/流速是否合理）。

输出三段：
  1. 前 20 个 SPAWN 动作：t / 敌人 / routeIndex / 该路线首检查点（看 WAIT 是否与波次 preDelay 重复）
  2. 有 WAIT_FOR_SECONDS 的打头检查点统计（多少个、时长分布、出现在序列第几位）
  3. 实测：每个敌人的 出生帧 → 首次移动帧 / 到达终点帧，以及导航距离与理论耗时
"""
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim import fp                               # noqa: E402
from ak_sim import scenario_h124 as S               # noqa: E402
from ak_sim.engine import Battle, build_schedule    # noqa: E402

FPS = 30


def main():
    b = Battle(S.LEVEL, seed=0, record=False)
    sched = build_schedule(b.level)
    spawns = [a for a in sched if a['type'] == 'SPAWN']
    print(f'SPAWN 动作 {len(spawns)} 个；时间范围 {spawns[0]["t"]:.1f}~{spawns[-1]["t"]:.1f}s')
    routes = b.level.get('routes') or []

    def first_cps(ri, n=3):
        if ri is None or ri >= len(routes) or not routes[ri]:
            return []
        out = []
        for cp in (routes[ri].get('checkpoints') or [])[:n]:
            out.append((cp.get('type'), cp.get('time'), cp.get('position')))
        return out

    print('\n=== 前 20 个 SPAWN：波次时刻 vs 路线首检查点 ===')
    for a in spawns[:20]:
        print(f'  t={a["t"]:7.1f}s wave={a["wave"]} frag={a["frag"]} route={a["route"]} '
              f'{a["key"]:<24} 首检查点={first_cps(a["route"])}')

    print('\n=== 检查点类型分布（全部路线）===')
    types = Counter()
    for rt in routes:
        for cp in (rt.get('checkpoints') or []):
            types[cp.get('type')] += 1
    print(' ', dict(types))

    # 以 WAIT 开头的路线：其 WAIT 时长 vs 该路线被使用的波次时刻
    print('\n=== 以 WAIT_FOR_SECONDS 开头的路线 ===')
    wait_lead = {}
    for i, rt in enumerate(routes):
        if not rt:
            continue
        cps = rt.get('checkpoints') or []
        if cps and cps[0].get('type') == 'WAIT_FOR_SECONDS':
            wait_lead[i] = float(cps[0].get('time') or 0.0)
    print(f'  共 {len(wait_lead)} 条：', {k: v for k, v in list(wait_lead.items())[:12]})
    used = Counter(a['route'] for a in spawns)
    for ri, wt in list(wait_lead.items())[:8]:
        ts = [a['t'] for a in spawns if a['route'] == ri]
        print(f'  route {ri}: WAIT {wt:.0f}s，被 {used[ri]} 个 SPAWN 使用，波次时刻 {ts[:4]}')

    # 实测穿行
    print('\n=== 实测：出生 → 首次移动 / 到达终点 ===')
    b2 = Battle(S.LEVEL, seed=0, record=False)
    born = {}
    first_move = {}
    arrived = {}
    orig_spawn = Battle._spawn_enemy

    def sp(self, a):
        n0 = len(self.units)
        orig_spawn(self, a)
        if len(self.units) > n0:
            uid = max(self.units)
            born[uid] = (self.frame, a['key'], a['route'])

    Battle._spawn_enemy = sp
    orig_tick = Battle.tick

    def tk(self):
        orig_tick(self)
        for uid, u in list(self.units.items()):
            if uid in born and uid not in first_move:
                if u.grid() != (int((u.route_end or (0, 0))[0]), int((u.route_end or (0, 0))[1])):
                    if (fp.to_float(u.pos[0]) % 1.0, fp.to_float(u.pos[1]) % 1.0) not in ((0.5, 0.5),):
                        first_move[uid] = self.frame

    Battle.tick = tk
    esc = []
    for _ in range(30 * 200):
        b2.tick()
        for l in b2.logs[-40:]:
            if l.kind in ('escape', 'civilian_arrived') and l.frame not in [e[0] for e in esc]:
                esc.append((l.frame, l.detail.get('enemy')))
    Battle._spawn_enemy = orig_spawn
    Battle.tick = orig_tick

    print('  按 UID 抽样（出生帧 / 首次离开出生格 / 路线起点→终点 导航距离 / 理论耗时）：')
    for uid in sorted(born)[:10]:
        f0, key, ri = born[uid]
        u = b2.units.get(uid)
        spd = fp.to_float(u.move_speed) * b2.move_multiplier if u else 0
        note = ''
        if u is not None:
            nm = b2.map.build_navmap(u.route_end, flying=u.flying)
            st = routes[ri].get('startPosition') if (ri is not None and ri < len(routes) and routes[ri]) else {}
            d = nm.get((int(st.get('row', -1)), int(st.get('col', -1))))
            if d:
                note = f'导航距离 {d:.1f} 格，理论 {d/spd:.1f}s' if spd else ''
        print(f'  uid={uid:>3} 出生 {f0/FPS:6.1f}s route={ri} {key:<22} '
              f'速度 {spd:.2f}格/s  首次移动 {first_move.get(uid, "-")} {note}')
    print('  前若干进点事件：', [(round(f / FPS, 1), n) for f, n in esc[:8]])


if __name__ == '__main__':
    main()
