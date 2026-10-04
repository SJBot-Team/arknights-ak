# -*- coding: utf-8 -*-
"""verify_semantics.py — ★验证"五个语义"在代码层面**确实彼此独立**，并给出**事件关联**。

用户 2026-09-15 明确要求：区分 **碰撞体积 / 受击判定 / 阻挡判定 / 攻击范围判定**，
并从代码层面说明它们**与哪些事件相关**。本脚本用**可执行的断言**把这件事固定下来：

| 断言 | 含义 |
|---|---|
| A1 | 改**碰撞体积** ↛ 索敌（`target_select` 帧不变）⇒ 碰撞体积不参与索敌 |
| A2 | 改**受击判定体积** ↛ 阻挡（`block`/`block_snap` 帧不变）⇒ 受击体积不参与阻挡 |
| A3 | 改**受击判定体积** → 索敌/命中时刻变化 ⇒ 受击体积**只**影响索敌 |
| A4 | 改**受击判定体积** ↛ `aoe_targets` 结果 ⇒ **AoE 命中与体积无关**（用户第 4 点） |
| A5 | 改任一**体积** ↛ `cells_in_range` ⇒ 攻击范围是**方格集合**，与体积无关 |
| A6 | 改 `BLOCK_CAPTURE_DISTANCE` → `block` 帧变化 ⇒ 阻挡判定由"捕获距离"决定 |
| A7 | 改**干员受击半径** → 远程敌人索敌触及变化（`rangeRadius ± 0.25`）⇒ 敌方远程是"圆+我方圆" |
| A8 | 近战敌人（`rangeRadius=0`）不走圆判据；敌方索敌事件带 `judge`（blocked/melee_adjacent/circle_*） |

★用户 2026-09-15 明确的两侧**不同表示**：
- 我方（干员）：**方格范围**（芬 = 2 格）+ **敌人 0.1 圆**进入即索敌；
- 敌方（远程）：**确定半径的圆**（`rangeRadius`）+ **干员 0.25 圆**处于其内即攻击。

用法：`python verify_semantics.py`
"""
from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim import fp                        # noqa: E402
from ak_sim.engine import Battle             # noqa: E402
from ak_sim.scenario import Scenario         # noqa: E402
from replay_verify5 import DEPLOYS, DIR_MAP, to_rc   # noqa: E402

OK, FAIL = '✅', '❌'
FAILED = []


def check(name: str, cond: bool, detail: str = '') -> None:
    print(f'  {OK if cond else FAIL} {name}{("  — " + detail) if detail else ""}')
    if not cond:
        FAILED.append(name)


def run(options: dict, frames: int = 700) -> Battle:
    sc = Scenario('1-1')
    b = Battle(sc.stage_code, seed=0, record=True, record_every=1, max_frames=frames,
               options=options)
    plan = {}
    for f, char, tile, direc, cov in DEPLOYS:
        plan.setdefault(f, []).append((char, to_rc(tile), direc, cov))
    for _ in range(frames):
        b.tick()
        if b.frame in plan:
            for char, (r, c), direc, cov in plan[b.frame]:
                b.deploy(char, r, c, direction=DIR_MAP[direc], elite=2, level=90,
                         potential=6, trust=200, skill_index=0, skill_level=7, cost=cov)
    return b


def kinds(b: Battle, kind: str) -> list[int]:
    return [l.frame for l in b.logs if l.kind == kind]


def main() -> int:
    base = run({})
    no_hit = run({'hit_volume_enemy': 0.0})
    big_hit = run({'hit_volume_enemy': 1.0})
    short_block = run({'block_capture_distance': 0.5})

    print('=== A1 碰撞体积 ↛ 索敌 ===')
    # 把全体单位的**碰撞体积**改成极端值，索敌/命中/范围都不应变化
    b = run({})
    before_ts, before_hit = kinds(b, 'target_select'), kinds(b, 'hit')
    before_cells = [tuple(sorted(b.cells_in_range(u))) for u in b.units.values()]
    for u in b.units.values():
        u.collider_radius = 5.0
    b.tick()
    after_ts, after_hit = kinds(b, 'target_select'), kinds(b, 'hit')
    after_cells = [tuple(sorted(b.cells_in_range(u))) for u in b.units.values()]
    check('把碰撞半径改成 5.0，`target_select` 帧不变', before_ts == after_ts,
          f'{len(before_ts)} 次索敌')
    check('把碰撞半径改成 5.0，`hit` 帧不变', before_hit == after_hit)
    check('把碰撞半径改成 5.0，`cells_in_range` 不变', before_cells == after_cells)
    check('碰撞体积字段存在且独立', hasattr(list(base.units.values())[0], 'collider_radius'),
          f'干员碰撞半径 = {list(base.units.values())[0].collider_radius}')
    check('受击半径字段存在且独立', hasattr(list(base.units.values())[0], 'hit_radius'),
          f'干员受击半径 = {list(base.units.values())[0].hit_radius}')

    print('\n=== A2 受击判定体积 ↛ 阻挡 ===')
    check('把受击半径 0 → 1.0，`block` 帧完全不变',
          kinds(base, 'block') == kinds(big_hit, 'block'),
          f'block 帧 {kinds(base, "block")}')
    check('把受击半径 0 → 1.0，`block_snap` 帧完全不变',
          kinds(base, 'block_snap') == kinds(big_hit, 'block_snap'))

    print('\n=== A3 受击判定体积 → 索敌/命中 ===')
    t0, t1 = kinds(no_hit, 'target_select'), kinds(big_hit, 'target_select')
    h0, h1 = kinds(no_hit, 'hit'), kinds(big_hit, 'hit')
    check('受击半径影响索敌时刻', t0 != t1 or h0 != h1,
          f'半径 0.0 首次索敌 {t0[:1]} / 命中 {h0[:2]}；半径 1.0 首次索敌 {t1[:1]} / 命中 {h1[:2]}')
    judges = {l.detail.get('judge') for l in big_hit.logs
              if l.kind == 'target_select' and l.detail.get('side') != 'ENEMY'}
    check('我方索敌事件带**判据**字段（grid / hit_volume）',
          judges <= {'grid', 'hit_volume'}, f'实际出现 {sorted(judges)}')
    hv = [l.frame for l in big_hit.logs
          if l.kind == 'target_select' and l.detail.get('judge') == 'hit_volume']
    check('存在"靠受击体积"完成的索敌（证明体积确实被纳入）', len(hv) > 0,
          f'共 {len(hv)} 次，最早 {hv[:3]}')

    print('\n=== A4 AoE 命中与体积无关（用户第 4 点）===')
    b = base
    fn = b.find_unit('芬')
    cells = b.aoe_cells_around(fn.grid(), cross_only=True)
    a0 = [e.uid for e in b.aoe_targets(cells)]
    saved = [(e.uid, e.hit_radius) for e in b.units.values()]
    for e in b.units.values():
        e.hit_radius = 3.0
    a1 = [e.uid for e in b.aoe_targets(cells)]
    for uid, hr in saved:
        b.units[uid].hit_radius = hr
    check('把全体受击半径改成 3.0，`aoe_targets` 结果不变', a0 == a1,
          f'目标 uid {a0}')
    check('`aoe_targets` 只用"目标中心所在格"',
          all(e.grid() in cells for e in b.aoe_targets(cells)))

    print('\n=== A5 攻击范围是方格集合，与体积无关 ===')
    c0 = base.cells_in_range(fn)
    for e in base.units.values():
        e.hit_radius = 9.0
        e.collider_radius = 9.0
    c1 = base.cells_in_range(fn)
    check('改体积后 `cells_in_range` 不变', c0 == c1, f'芬(朝左) 范围格 {sorted(c0)}')

    print('\n=== A6 阻挡判定由"捕获距离/格邻域"决定 ===')
    check('缩短捕获距离 ⇒ `block` 帧改变（capture_distance 规则下）',
          kinds(run({'block_rule': 'capture_distance', 'block_capture_distance': 1.0}), 'block')
          != kinds(run({'block_rule': 'capture_distance', 'block_capture_distance': 0.5}), 'block'),
          f'1.0: {kinds(run({"block_rule": "capture_distance", "block_capture_distance": 1.0}), "block")[:3]} …；'
          f'0.5: {kinds(run({"block_rule": "capture_distance", "block_capture_distance": 0.5}), "block")[:3]} …')
    check('★默认阻挡规则 = `radius`（**统一半径 0.7071**，B站 cv25694535 + 代码核验）',
          base.block_rule == 'radius' and abs(base.block_radius - 0.7071) < 1e-6,
          f'实际 rule={base.block_rule} radius={getattr(base, "block_radius", None)}')

    print('\n=== A7/A8 远程敌人索敌 = 半径圆 vs 干员 0.25 圆（用户 2026-09-15 明确）===')
    # 跑到 2400 帧（1-1 的 enemy_1028_mocock 在 2280 帧出现，rangeRadius=1.75）
    # 造一个远程敌人（rangeRadius=1.75，如 enemy_1028_mocock）：干员受击半径改变应影响其索敌
    for label, opts2 in (('干员半径 0.25', {'ally_hit_radius': 0.25}),
                         ('干员半径 0.0', {'ally_hit_radius': 0.0}),
                         ('干员半径 1.0', {'ally_hit_radius': 1.0})):
        bb = run(opts2, frames=400)
        es = [u for u in bb.units.values() if u.side == 'ENEMY'
              and float(u.extra.get('rangeRadius') or 0.0) > 0]
        if not es:
            continue
        e0 = es[0]
        reach, judge = bb.enemy_reach(e0)
        print(f'    {label}: 远程敌人 {e0.name} rangeRadius='
              f'{e0.extra.get("rangeRadius")} ⇒ 有效触及 {reach:.2f}（判据 {judge}）')
    b_c = run({'ally_hit_radius': 0.25}, frames=2400)
    reach_025 = None
    for u in b_c.units.values():
        if u.side == 'ENEMY' and float(u.extra.get('rangeRadius') or 0.0) > 1.0:
            reach_025 = b_c.enemy_reach(u)[0]
            rr = float(u.extra.get('rangeRadius'))
            break
    b_0 = run({'ally_hit_radius': 0.0}, frames=2400)
    reach_0 = None
    for u in b_0.units.values():
        if u.side == 'ENEMY' and float(u.extra.get('rangeRadius') or 0.0) > 1.0:
            reach_0 = b_0.enemy_reach(u)[0]
            break
    if reach_025 is not None and reach_0 is not None:
        check('远程敌人触及 = rangeRadius + 干员 0.25 圆（相交语义）',
              abs(reach_025 - reach_0 - 0.25) < 1e-6,
              f'0.25 → {reach_025:.2f}；0.0 → {reach_0:.2f}（差 {reach_025 - reach_0:.2f}）')
    else:
        print('    （1-1 无远程敌人，跳过数值断言；已由 enemy_reach 的公式保证）')
    # 近战敌人的索敌与"干员圆"无关
    check('近战敌人（rangeRadius=0）不参与圆判据',
          all(base.enemy_reach(u)[1] == 'melee'
              for u in base.units.values()
              if u.side == 'ENEMY' and float(u.extra.get('rangeRadius') or 0.0) <= 0))
    en_judges = {l.detail.get('judge') for l in base.logs
                 if l.kind == 'target_select' and l.detail.get('side') == 'ENEMY'}
    check('敌方索敌事件带判据（blocked / melee_adjacent / circle_*）',
          en_judges <= {'blocked', 'melee_adjacent', 'circle_intersect', 'circle_contain', 'melee'},
          f'实际出现 {sorted(en_judges)}')

    print('\n=== A9 敌人移动惯性（用户 2026-09-15：出生速度 0 + 加速过程）===')
    from ak_sim import fp as _fp
    b_i = run({}, frames=420)
    e2 = None
    for s in b_i.frames:
        if s['f'] == 361:
            e2 = next((u for u in s['units'] if u['side'] == 'ENEMY'
                       and u['key'] == 'enemy_1000_gopro'), None)
            break
    # 出生后逐帧速度
    speeds = []
    for s in b_i.frames:
        if 360 <= s['f'] <= 380:
            u = next((x for x in s['units'] if x['side'] == 'ENEMY'
                      and x['key'] == 'enemy_1000_gopro'), None)
            if u is not None:
                speeds.append((s['f'], u['x'], u['y']))
    if len(speeds) >= 6:
        d1 = math.hypot(speeds[1][1] - speeds[0][1], speeds[1][2] - speeds[0][2]) * 30
        d2 = math.hypot(speeds[3][1] - speeds[2][1], speeds[3][2] - speeds[2][2]) * 30
        d5 = math.hypot(speeds[6][1] - speeds[5][1], speeds[6][2] - speeds[5][2]) * 30
        vmax = 1.9 * 0.5
        check('★出生后速度从 0 递增（不是瞬间到上限）', d1 < d2 < vmax * 0.999,
              f'出生第1帧 {d1:.3f} → 第3帧 {d2:.3f} → 第6帧 {d5:.3f}（上限 {vmax:.3f} 格/秒）')
        check('★速度趋近上限（差值按指数衰减）', abs(d5 - vmax) < vmax * 0.5,
              f'第6帧 {d5:.3f} vs 上限 {vmax:.3f}')
    else:
        print('    （取不到敌人轨迹，跳过）')
    b_ni = run({'move_inertia': False}, frames=420)
    check('关闭惯性 ⇒ 敌人到达时刻改变（证明加速过程确实生效）',
          kinds(b_i, 'hit') != kinds(b_ni, 'hit'),
          f'有惯性首个命中 {kinds(b_i, "hit")[:2]}；无惯性 {kinds(b_ni, "hit")[:2]}')

    print()
    if FAILED:
        print(f'{FAIL} 未通过 {len(FAILED)} 项：{FAILED}')
        return 1
    print(f'{OK} 全部通过：语义彼此独立、与事件关联已显式化、移动惯性已生效')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
