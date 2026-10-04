# -*- coding: utf-8 -*-
"""diag_summon.py — 诊断令 S3 召唤物 AoE 为何不触发。

检查链：
  1. 轴表里是否真的有召唤物部署操作（unit 名 / 落地帧 / 坐标）
  2. 部署后 u.is_token 与 u.extra['owner'] 是否正确
  3. owner 解析（self.units.get(owner_uid)）是否命中
  4. 令技能生效窗口（skill_active 的帧区间）
  5. 每个召唤物在 owner 技能期间，其「上下左右四格」内敌人的逐帧计数
"""
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim import scenario_h124 as S            # noqa: E402
from ak_sim.axis import parse_cyberplastic        # noqa: E402
from ak_sim.engine import Battle                  # noqa: E402

FPS = 30


def main():
    ax = parse_cyberplastic(S.XLSM)
    print('=== 轴表全部操作（unit / coord / 解析帧）===')
    ops = []
    for o in ax.ops:
        d = o.to_dict()
        d['char'] = S.NAME_MAP.get(o.unit, o.unit)
        for k, v in S.UNIT_CONFIG.get(d['char'], {}).items():
            d.setdefault(k, v)
        ops.append(d)
    plan = ax.resolve_frames(initial_cost=10.0, unit_costs={}, timebase='abs-seconds')
    for i, (o, p) in enumerate(zip(ops, plan)):
        print(f'  [{i:02d}] {p["frame"]:>5}f ({p["frame"]/FPS:6.1f}s) {o["op"]:<8} '
              f'{o.get("unit")}  {o.get("coord","")}  dir={o.get("dir","")}')
    print(f'  → 其中 deploy 召唤物：'
          f'{[o.get("unit") for o in ops if str(o.get("unit","")).startswith("token_")]}')

    b = Battle(S.LEVEL, seed=0, record=False)
    print(f'\n=== token_owner_map（召唤物 → 拥有者 charId）===')
    for k, v in b.token_owner_map.items():
        print(f'  {k} → {v}')

    # --- 逐帧钩子：记录 token 状态与邻格敌人数 ---
    token_trace = defaultdict(list)     # uid -> [(frame, alive, owner_uid, skill_active, n_neighbors)]
    orig_tick = Battle.tick

    def traced_tick(self):
        orig_tick(self)
        for uid, u in list(self.units.items()):
            if getattr(u, 'is_token', False):
                owner = self.units.get(u.extra.get('owner'))
                tr, tc = u.grid()
                cells = {(tr - 1, tc), (tr + 1, tc), (tr, tc - 1), (tr, tc + 1)}
                n = sum(1 for e in self.units.values()
                        if e.side == 'ENEMY' and e.alive and e.grid() in cells)
                token_trace[uid].append((self.frame, u.alive, u.extra.get('owner'),
                                         bool(owner and owner.skill_active), n))

    Battle.tick = traced_tick
    fired = b.run_axis(ops, name_map=S.NAME_MAP, coord_transform=S.COORD_TRANSFORM,
                       max_frames=30 * 400, continue_after_fail=True,
                       retry_on_cost=True, retry_on_sp=False,
                       schedule=[int(p['frame']) for p in plan])
    Battle.tick = orig_tick

    print(f'\n=== 召唤物部署操作触发情况 ===')
    for x in fired:
        if str(x.get('unit', '')).startswith('token_'):
            print(f'  {x}')

    print(f'\n=== 召唤物实例（{len(token_trace)} 个 uid）===')
    for uid, tr in token_trace.items():
        if not tr:
            continue
        u = b.units.get(uid)
        f0, f1 = tr[0][0], tr[-1][0]
        alive_frames = sum(1 for r in tr if r[1])
        owner_active = sum(1 for r in tr if r[3])
        with_enemy = sum(1 for r in tr if r[3] and r[4] > 0)
        print(f'  uid={uid} name={getattr(u, "name", "?")} grid={u.grid() if u else "?"} owner={tr[0][2]} '
              f'帧 {f0}~{f1}（{f0/FPS:.1f}~{f1/FPS:.1f}s） 存活 {alive_frames}f '
              f'owner技能生效 {owner_active}f  其中邻格有敌 {with_enemy}f')
        # 邻格敌人数峰值
        peak = max((r[4] for r in tr), default=0)
        print(f'      邻格敌人数峰值 {peak}；最终 uid 是否仍在 units 中：{uid in b.units}')

    print(f'\n=== 令 skill_active 窗口 ===')
    ling_uid = None
    for uid, u in b.units.items():
        if getattr(u, 'name', '') == '令':
            ling_uid = uid
    print(f'  令 uid={ling_uid}')
    evts = [l for l in b.logs if l.kind in ('skill_charge', 'skill_on', 'skill_end', 'skill_reject')
            and l.detail.get('unit') in ('令',)]
    for l in evts:
        print(f'    {l.frame:>5}f ({l.frame/FPS:6.1f}s) {l.kind} {l.detail}')
    # 直接扫描 trace：任意 token 的 owner_uid 与 ling_uid 的关系
    owners = {tr[0][2] for tr in token_trace.values() if tr}
    print(f'  召唤物记录的 owner uid 集合 = {owners}')

    print(f'\n=== 日志统计 ===')
    k = Counter(l.kind for l in b.logs)
    for kind in ('deploy_failed', 'summon_charge', 'summon_aoe', 'hit', 'kill', 'escape',
                 'device_destroyed', 'civilian_arrived', 'skill_reject', 'token_deployed'):
        if k.get(kind):
            print(f'  {kind}: {k[kind]}')
    print(f'  全部 kind：{dict(k)}')
    print(f'\n战果 {b.result} 生命 {b.life} 帧 {b.frame}')

    # --- 采样若干帧：召唤物位置 vs 敌人实际位置 ---
    print('\n=== 敌人实际行进轨迹（每 300 帧采样一次，只列前 8 个存活敌人）===')
    b2 = Battle(S.LEVEL, seed=0, record=False)
    samples = []
    orig2 = Battle.tick

    def tick2(self):
        orig2(self)
        if self.frame % 300 == 0:
            es = [(u.name, u.grid()) for u in self.units.values()
                  if u.side == 'ENEMY' and u.alive]
            samples.append((self.frame, es[:8], len(es)))

    Battle.tick = tick2
    b2.run_axis(ops, name_map=S.NAME_MAP, coord_transform=S.COORD_TRANSFORM,
                max_frames=30 * 400, continue_after_fail=True,
                retry_on_cost=True, retry_on_sp=False,
                schedule=[int(p['frame']) for p in plan])
    Battle.tick = orig2
    for f, es, n in samples[:20]:
        print(f'  {f:>5}f ({f/FPS:6.1f}s) 存活敌 {n:>3} 前几个：(row,col) {es}')


if __name__ == '__main__':
    main()
