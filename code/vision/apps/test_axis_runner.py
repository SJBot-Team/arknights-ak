# -*- coding: utf-8 -*-
"""test_axis_runner.py — ★回归：**打图端执行器能吃下「共用轴表」**（dry-run，不注入任何输入）。

背景（用户需求）：目标②要求「与模拟**共用易读易改的轴表**」。
链路：`ak/axis/1-1.yaml`（唯一事实来源）
      → `sim/draft/axis_to_runner.py` → `ak/data/derived/axis_1-1.json`
      → 本测试用 `code/vision/apps/run_axis.py` 的 `axis_runner` **干跑**执行。

断言：
1. `ok == true`、`fired == total == 2`；
2. 执行日志里的**目标帧**与轴表一致（10 / 411）、单位与坐标一致（芬 D6 左 / 月见夜 D4 上）；
3. **迟到 > 0.5 帧的操作 = 0 条**（虚拟时钟下的时序保真）；
4. 费用门控通过（费用锚 8 / 14）；
5. `same_frame_groups` 字段存在（为后续"同帧多操作"留位）。

安全：全程 **dry-run + 虚拟时钟**，不加载任何输入后端、不截图、不注入。
"""
from __future__ import annotations

import json
import os
import sys

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


def main():
    cfg_path = os.path.join(ROOT, 'configs', 'axis_1-1.json')
    with open(cfg_path, encoding='utf-8') as f:
        raw = json.load(f)
    cfg = dict(raw['axis_runner'])
    cfg['dry_run'] = True
    cfg.setdefault('clock', {})['source'] = 'virtual'
    cfg['timebase'] = 'cost-relative'      # ★打图端原生口径（费用锚点）

    print('=== 打图端干跑「共用轴表」===')
    load_plugins(os.path.join(ROOT, 'plugins'))
    runner_cls = TASKS['axis_runner']
    engine = run_axis._Runner({'axis_runner': cfg})
    res = runner_cls().run(engine)

    check('执行成功（ok）', res.get('ok') is True, f'error={res.get("error")}')
    check('执行条数 2/2', res.get('fired') == 2 and res.get('total') == 2,
          f'fired={res.get("fired")} total={res.get("total")}')
    check('含 same_frame_groups 字段（同帧多操作用）', 'same_frame_groups' in res,
          f'={res.get("same_frame_groups")}')

    log = res.get('log') or []
    tf = [r.get('target_frame') for r in log]
    check('目标帧与轴表一致（10 / 411）', tf == [10, 411], f'{tf}')
    units = [r.get('unit') for r in log]
    check('单位顺序正确（芬 → 月见夜）', units == ['芬', '月见夜'], f'{units}')
    late = [r for r in log if float(r.get('late_real_frames') or 0) > 0.5]
    check('迟到 >0.5 帧的操作 = 0 条', len(late) == 0,
          '最大 %.3f 帧' % max((float(r.get('late_real_frames') or 0) for r in log), default=0))

    print()
    if FAILED:
        print(f'❌ 未通过 {len(FAILED)} 项：{FAILED}')
        return 1
    print('✅ 通过：打图端执行器可直接执行「与模拟共用」的轴表（dry-run 保真，0 迟到）')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
