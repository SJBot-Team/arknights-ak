# -*- coding: utf-8 -*-
"""test_same_frame.py — ★回归：**同帧多操作**（"操作前先步进/暂停定位帧再执行"）。

## 需求（目标②）
> 「**同帧多操作**（操作前先步进/暂停定位帧再执行）」

## 本测试
用一份**合成轴表**（两条部署落在**同一目标帧**）跑两种模式并对比：

| 模式 | 期望 |
|---|---|
| `same_frame_mode='sequential'`（默认） | 逐条执行，`frozen` 字段为 False（保留既有语义） |
| **`same_frame_mode='freeze'`** | **一组冻结**内下发两条：`frozen_groups=1`、`frozen_ops=2`、两条 `group_id` 相同、`frozen_frame` = 目标帧、`frozen_mode='sim'` |

冻结控制器用 `mode='sim'`（**dry-run/离线**）：不做任何输入，只记录"冻结帧"，
⇒ 可在**无游戏**的情况下验证"同帧多操作"的控制流与可审计字段。

安全：全程 dry-run + 虚拟时钟；`sim` 冻结模式**不加载任何输入后端、不截图、不注入**。
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding='utf-8')

from kernel.registry import TASKS, load_plugins     # noqa: E402
import run_axis                                     # noqa: E402

FAILED = []


def check(name, cond, detail=''):
    print(f'  {"✅" if cond else "❌"} {name}{("  — " + detail) if detail else ""}')
    if not cond:
        FAILED.append(name)


def _axis(tmp: str) -> str:
    """合成轴表：**两条部署在同一帧 411**。"""
    ops = [
        {'op': 'deploy', 'unit': '芬', 'coord': 'D6', 'dir': '左',
         'frame': 411, 'abs_seconds': 411 / 30.0},
        {'op': 'deploy', 'unit': '月见夜', 'coord': 'D4', 'dir': '上',
         'frame': 411, 'abs_seconds': 411 / 30.0},
    ]
    p = os.path.join(tmp, 'axis_sameframe.json')
    with open(p, 'w', encoding='utf-8') as f:
        json.dump({'level': 'selftest', 'timebase': 'frame', 'seed': 0,
                   'meta': {'source': 'test_same_frame.py（合成）'}, 'ops': ops},
                  f, ensure_ascii=False)
    return p


def _run(tmp: str, mode: str) -> dict:
    cfg = {
        'axis': _axis(tmp), 'dry_run': True, 'timebase': 'abs-seconds',
        'clock': {'source': 'virtual'}, 'initial_cost': 99, 'frames_per_cost': 30,
        'unit_costs': {'芬': 8, '月见夜': 14}, 'grid': {'rows': 7, 'cols': 9},
        'coord_transform': 'rc_normal', 'cost_gate': False, 'sp_gate': False,
        'max_seconds': 30, 'loop_hz': 240, 'same_frame_mode': mode,
        'virtual_speed': 8.0,       # 虚拟时钟加速（离线测试用，不影响帧号语义）
        'freeze': {'mode': 'sim'},
    }
    load_plugins(os.path.join(ROOT, 'plugins'))
    runner_cls = TASKS['axis_runner']
    engine = run_axis._Runner({'axis_runner': cfg})
    return runner_cls().run(engine)


def main():
    with tempfile.TemporaryDirectory() as tmp:
        print('=== A) 默认顺序模式（same_frame_mode="sequential"）===')
        a = _run(tmp, 'sequential')
        check('执行成功', a.get('ok') is True, f'error={a.get("error")}')
        la = a.get('log') or []
        check('两条都执行', len(la) == 2, f'{len(la)} 条')
        check('未启用冻结（frozen 全为 False）',
              all(not r.get('frozen') for r in la))
        check('结果为 same_frame_groups=1（同帧被识别）',
              a.get('same_frame_groups') == 1, f'={a.get("same_frame_groups")}')

        print('\n=== B) ★冻结模式（same_frame_mode="freeze"）===')
        b = _run(tmp, 'freeze')
        check('执行成功', b.get('ok') is True, f'error={b.get("error")}')
        lb = b.get('log') or []
        check('两条都执行', len(lb) == 2, f'{len(lb)} 条')
        check('★冻结组数 = 1', b.get('frozen_groups') == 1, f'={b.get("frozen_groups")}')
        check('★冻结内操作数 = 2', b.get('frozen_ops') == 2, f'={b.get("frozen_ops")}')
        check('★无冻结失败', b.get('frozen_mismatch') == 0, f'={b.get("frozen_mismatch")}')
        check('两条同属一个 group_id',
              len({r.get('group_id') for r in lb}) == 1 and lb[0].get('group_id'),
              f'{ [r.get("group_id") for r in lb] }')
        check('group_size = 2', all(r.get('group_size') == 2 for r in lb))
        check('★冻结帧 = 目标帧 411',
              all(r.get('frozen') is True and r.get('frozen_frame') == 411.0 for r in lb),
              f'{ [r.get("frozen_frame") for r in lb] }')
        check('冻结模式记录为 sim（离线模拟，不注入）',
              all(r.get('frozen_mode') == 'sim' for r in lb))
        check('返回体带 same_frame_mode', b.get('same_frame_mode') == 'freeze')

        print('\n=== C) ★这正是"冻结模式"存在的理由 ===')
        tf_a = [r['target_frame'] for r in la]
        tf_b = [r['target_frame'] for r in lb]
        check('★冻结模式下两条的 target_frame **完全相同**且 = 411',
              tf_b == [411, 411], f'{tf_b}')
        check('顺序模式下两条可按各自时序漂移（≥411 即可）',
              all(v >= 411 for v in tf_a), f'{tf_a}')
        check('★冻结模式保证"同帧"：两条的 frozen_frame 一致',
              len({r.get('frozen_frame') for r in lb}) == 1, f'{tf_b}')

    print()
    if FAILED:
        print(f'❌ 未通过 {len(FAILED)} 项：{FAILED}')
        return 1
    print('✅ 通过：同帧多操作在"冻结模式"下成组执行、字段可审计；顺序模式无回归')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
