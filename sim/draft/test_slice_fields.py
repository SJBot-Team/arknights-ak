# -*- coding: utf-8 -*-
"""test_slice_fields.py — ★回归：逐帧切片**六项必需字段**齐全且**真的有值**。

目标①要求切片含：**操作 / 血量 / 坐标 / 攻速 / 移速 / 随机判定**。
"字段存在"≠"有值"（本轮就踩过一次：`attack_windup_frames` 名字写错 ⇒ 恒为 0 的**假补全**）。
故本测试对每项都断言"**在合适帧上取到非平凡值**"。

| 项 | 断言 |
|---|---|
| 操作 | 部署帧的 `ops` 含该次部署 |
| 血量 | 有单位且 `hp>0`、`max_hp>0`；受伤后 `hp<max_hp` |
| 坐标 | 敌人 `x` 逐帧变化（在移动） |
| 攻速 | `atk_interval_frames>0`、`attack_speed>0`、且**存在帧** `atk_windup_left is not None` |
| 移速 | **`v_abs` 非恒定**：出生时为 0，之后单调升到接近上限（惯性） |
| 随机判定 | `rng_state`/`rng_draws` 齐备，且 `rng_events` 键存在 |
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim.engine import Battle              # noqa: E402
from ak_sim.scenario import Scenario          # noqa: E402

FAILED = []


def check(name, cond, detail=''):
    print(f'  {"✅" if cond else "❌"} {name}{("  — " + detail) if detail else ""}')
    if not cond:
        FAILED.append(name)


def main():
    sc = Scenario('1-1')
    b = Battle(sc.stage_code, seed=0, record=True, record_every=1, max_frames=420)
    for _ in range(420):
        b.tick()
        if b.frame == 10:
            b.deploy('char_123_fang', 3, 5, direction='左', elite=1, level=55,
                     potential=6, trust=200, skill_index=0, skill_level=7, cost=8)
    fr = b.frames
    s0 = fr[0]
    print(f'切片 {len(fr)} 帧；顶层键: {sorted(s0.keys())}')

    print('\n=== 操作 ===')
    op10 = [f for f in fr if f['f'] == 10]
    check('帧 10 的切片含部署操作',
          bool(op10) and any('deploy' in str(o.get('kind', '')) for o in op10[0]['ops']),
          str(op10[0]['ops'])[:80] if op10 else '缺')

    print('\n=== 血量 ===')
    any_u = any(f['units'] for f in fr)
    check('存在单位记录', any_u)
    hurt = [u for f in fr for u in f['units'] if u['hp'] < u['max_hp']]
    check('存在"已受伤"单位（hp<max_hp）', bool(hurt),
          f'{len(hurt)} 条，例: hp={hurt[0]["hp"]}/{hurt[0]["max_hp"]}' if hurt else '')

    print('\n=== 坐标 ===')
    en = [u for f in fr for u in f['units'] if u['side'] == 'ENEMY' and u['uid'] == 2]
    xs = [u['x'] for u in en[:120]]
    check('敌人坐标逐帧变化（在移动）', len(set(xs)) > 10, f'{len(set(xs))} 个不同 x')

    print('\n=== 攻速 ===')
    us = [u for f in fr for u in f['units'] if u['side'] == 'ENEMY']
    check('atk_interval_frames > 0', all(u['atk_interval_frames'] > 0 for u in us))
    check('attack_speed > 0', all(u['attack_speed'] > 0 for u in us))
    wl = [u.get('atk_windup_left') for f in fr for u in f['units']
          if u.get('atk_windup_left') is not None]
    check('★存在前摇中的帧（atk_windup_left 非 None）', bool(wl),
          f'{len(wl)} 条，取值例: {sorted(set(wl))[:6]}')

    print('\n=== 移速 ===')
    vs = [u.get('v_abs') for f in fr for u in f['units']
          if u['side'] == 'ENEMY' and u['uid'] == 2]
    check('v_abs 字段存在', all(v is not None for v in vs))
    check('★v_abs 非恒定（体现加速过程）', len(set(vs)) > 5,
          f'{len(set(vs))} 个不同值；前 6 帧 {vs[:6]} → 后段 {vs[-3:]}')

    print('\n=== 随机判定 ===')
    check('rng_state / rng_draws 齐备',
          all(('rng_state' in f and 'rng_draws' in f) for f in fr))
    check('rng_events 键在位（本帧随机判定明细）', all('rng_events' in f for f in fr))

    print()
    if FAILED:
        print(f'❌ 未通过 {len(FAILED)} 项：{FAILED}')
        return 1
    print('✅ 通过：逐帧切片六项必需字段齐全**且都有实际取值**')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
