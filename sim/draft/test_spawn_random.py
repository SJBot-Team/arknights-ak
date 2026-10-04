# -*- coding: utf-8 -*-
"""test_spawn_random.py — ★验证"加权随机出怪组"（`randomSpawnGroupKey` + `weight`）。

## 背景（先摸底得到的结论）
- `probe_schedule_fields.py` 普查本地 15 个关卡：**只有肉鸽 1-1** 用了
  `randomSpawnGroupKey`（g1/g2/g3）+ `weight`（17 条动作）；
  主线/h12-4 全部为默认 ⇒ **静态时间轴对它们够用**。
- 语义（依 cpp `ActionData` 字段 + `IItemWithWeight.get_weightValue`）：
  **同一 group 内动作互斥，整组按 weight 加权抽一个**；`key` 为空串 = 抽到则不刷怪。

## 本测试
1. **同 seed 完全可复现**（两次运行出怪列表逐条相同）；
2. **不同 seed 会改变抽签结果**（至少有一个 group 换人）；
3. **抽签事件被记录**（`spawn_random_pick`，含 group/key/weight/weights）。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim.engine import Battle, build_schedule   # noqa: E402
from ak_sim import data as D                        # noqa: E402

LEVELS = os.path.join(D.AKGD, 'levels')
ROGUE = 'obt/roguelike/ro1/level_rogue1_1-1'
FAILED = []


def check(name, cond, detail=''):
    print(f'  {"✅" if cond else "❌"} {name}{("  — " + detail) if detail else ""}')
    if not cond:
        FAILED.append(name)


def spawn_list(seed: int, frames: int = 300):
    b = Battle(ROGUE, seed=seed, record=False, max_frames=frames)
    return b.schedule


def main():
    print('=== 1) 肉鸽 1-1：随机出怪组抽签 ===')
    s1 = spawn_list(0)
    s2 = spawn_list(0)
    key = [(a['t'], a.get('key'), a.get('wave'), a.get('frag'))
           for a in s1 if a.get('t') is not None]
    key2 = [(a['t'], a.get('key'), a.get('wave'), a.get('frag'))
            for a in s2 if a.get('t') is not None]
    print(f'  出怪条目 {len(key)} 条；抽签组 '
          f'{[a["group"] for a in s1 if a.get("type") == "__RANDOM_PICK__"]}')
    check('同 seed 两次运行出怪列表完全一致', key == key2)

    b = Battle(ROGUE, seed=0, record=False, max_frames=10)
    picks = [l for l in b.logs if l.kind == 'spawn_random_pick']
    check('抽签事件被记录（spawn_random_pick）', len(picks) > 0,
          f'{len(picks)} 条：' + ', '.join(
              f'{p.detail["group"]}→{p.detail["key"] or "(空=不刷怪)"}' for p in picks))

    print('\n=== 2) 不同 seed 会改变抽签 ===')
    diff = []
    for sd in (0, 1, 2, 3, 7, 12345):
        sk = [(a['t'], a.get('key')) for a in spawn_list(sd) if a.get('t') is not None]
        if sk != key:
            diff.append(sd)
    check('存在能改变出怪列表的 seed', len(diff) > 0,
          f'改动的 seed: {diff[:5]}（共 {len(diff)}/6）')

    print('\n=== 3) 主线/h12-4 不含随机组（静态时间轴足够） ===')
    for rel in ('obt/main/level_main_01-01', 'obt/hard/level_hard_12-04'):
        lv = D.load_level(rel)
        n = sum(1 for w in (lv.get('waves') or [])
                for fr in (w.get('fragments') or [])
                for a in (fr.get('actions') or []) if a.get('randomSpawnGroupKey'))
        check(f'{rel} 无 randomSpawnGroupKey', n == 0, f'{n} 条')

    print()
    if FAILED:
        print(f'❌ 未通过 {len(FAILED)} 项：{FAILED}')
        return 1
    print('✅ 全部通过：加权随机出怪组可复现、可审计；主线关卡不受影响')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
