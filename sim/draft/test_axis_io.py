# -*- coding: utf-8 -*-
"""test_axis_io.py — ★共用轴表的自检（模拟器 / 打图端 / 校验器三方一致性）。

断言：
1. `ak/axis/1-1.yaml` 可载入，必要段齐全；
2. `axis_to_deploy_plan` 给出 2 次部署，且 **帧 10 → 芬 @(3,5) 左 8 费**、**帧 411 → 月见夜 @(3,3) 上 14 费**
   （与标定表逐项一致）；
3. `axis_expect_table` 18 条；**显式 `n` 生效**（帧 461 那条的 n = 1）；
4. `video_to_game` 用锚点能还原硬锚点（video 621 → game 10 等）；
5. **打图端与模拟器读同一份 YAML** ⇒ 二者拿到的部署计划完全相同。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from axis_io import (axis_expect_table, axis_path, axis_to_derived,  # noqa: E402
                     axis_to_runner_ops, cells_letter_to_rc, load_axis,
                     axis_to_deploy_plan, video_to_game)

FAILED = []


def check(name, cond, detail=''):
    print(f'  {"✅" if cond else "❌"} {name}{("  — " + detail) if detail else ""}')
    if not cond:
        FAILED.append(name)


def main():
    print('=== 1) 载入与字段 ===')
    p = axis_path('1-1')
    check('轴表文件存在', os.path.exists(p), p)
    ax = load_axis('1-1')
    for k in ('stage', 'level', 'squad', 'deploys', 'expect', 'video_axis'):
        check(f'含 `{k}` 段', k in ax)

    print('\n=== 2) 部署计划（模拟器 / 打图端共用）===')
    plan = axis_to_deploy_plan(ax)
    check('部署次数 = 2', len(plan) == 2, f'{sorted(plan.keys())}')
    d10 = plan.get(10, [])
    d411 = plan.get(411, [])
    check('帧 10 → 芬 @(3,5) 朝左 8 费',
          d10 and d10[0][0] == 'char_123_fang' and d10[0][1] == (3, 5)
          and d10[0][2] == '左' and d10[0][3] == 8,
          f'{d10}')
    check('帧 411 → 月见夜 @(3,3) 朝上 14 费',
          d411 and d411[0][0] == 'char_283_midn' and d411[0][1] == (3, 3)
          and d411[0][2] == '上' and d411[0][3] == 14,
          f'{d411}')
    check('格子记法 D6→(3,5)、D4→(3,3)', cells_letter_to_rc('D6') == (3, 5)
          and cells_letter_to_rc('D4') == (3, 3))

    print('\n=== 3) 期望事件表（校验器）===')
    table = axis_expect_table(ax)
    check('18 条期望事件', len(table) == 18, f'{len(table)}')
    kinds = {t['kind'] for t in table}
    check('类别覆盖 spawn/dmg/kill/block', kinds == {'spawn', 'dmg', 'kill', 'block'},
          f'{sorted(kinds)}')
    e461 = [t for t in table if t['frame'] == 461]
    check('★显式 `n: 1` 生效（帧 461 猎狗命中芬）', e461 and e461[0]['n'] == 1,
          f'{e461[0] if e461 else None}')
    auto = [t for t in table if t['frame'] == 255]
    check('未写 `n` 时自动累计（帧 255 = 第 1 次）', auto and auto[0]['n'] == 1)

    print('\n=== 4) 视频帧 ↔ 游戏帧（打图端对轴）===')
    for v, g in ((621, 10), (4618, 411), (5961, 581), (8878, 1333)):
        got = video_to_game(ax, v)
        check(f'video {v} → game {g}', got == g, f'实得 {got}')

    print('\n=== 5) 三方读同一份文件 ===')
    ax2 = load_axis('1-1')
    check('两次载入的部署计划一致（同一事实来源）',
          axis_to_deploy_plan(ax) == axis_to_deploy_plan(ax2))

    print('\n=== 6) 打图端桥接（共用轴表 → 执行器 ops）===')
    ops = axis_to_runner_ops(ax)
    check('生成 2 条 ops', len(ops) == 2, f'{[o["op"] for o in ops]}')
    check('打图端字段齐全（op/unit/coord/dir/cost/frame/abs_seconds）',
          all(set(('op', 'unit', 'coord', 'dir', 'cost', 'frame', 'abs_seconds')) <= set(o)
              for o in ops if o['op'] == 'deploy'), f'{ops[0]}')
    check('abs_seconds = frame/30', abs(ops[0]['abs_seconds'] - ops[0]['frame'] / 30.0) < 1e-9,
          f"frame {ops[0]['frame']} → {ops[0]['abs_seconds']:.3f}s")
    d = axis_to_derived(ax)
    check('派生轴表结构 = {level,timebase,seed,meta,ops}',
          set(d) == {'level', 'timebase', 'seed', 'meta', 'ops'}, f'{sorted(d)}')

    print()
    if FAILED:
        print(f'❌ 未通过 {len(FAILED)} 项：{FAILED}')
        return 1
    print('✅ 通过：共用轴表可供模拟器 / 打图端 / 校验器三方一致读取')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
