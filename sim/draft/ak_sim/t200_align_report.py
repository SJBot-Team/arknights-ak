# -*- coding: utf-8 -*-
r"""t200_align_report.py — **模拟环境 vs 1-1 标定：逐事件对齐与残差报告**（T-200c）

输出：
  1. 部署对齐（帧 10 / 411 是否按轴表执行、费用是否吻合）
  2. 逐事件对照表：标定帧 → 模拟器最近同类事件 → Δ帧
  3. 汇总统计（Δ 分布、最大残差、命中率）
用法：python t200_align_report.py [--mode frame_ceil|fp_accumulate|floor|round]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim.engine import Battle                 # noqa: E402
from ak_sim.events import extract_events         # noqa: E402
from ak_sim.scenario import Scenario             # noqa: E402

STAGE = '1-1'
FANG = 'char_123_fang'
MIDN = 'char_283_midn'
DEPLOYS = [(10, FANG, 'D6', '左', 8), (411, MIDN, 'D4', '上', None)]
DIR_MAP = {'左': '左', '上': '上'}

# 标定表（`C:\Users\23922\Desktop\1-1标定.xlsx` → `04/54 §五`）
# (帧, 单位, 描述, 匹配谓词)
#   谓词：{'type': (允许的事件类型…), 'src': 攻击者名, 'tgt': 目标名, 'by': 击杀者}
#   ★必须带攻守限定：否则"芬命中"与"猎狗命中"会互相配错（首版就踩了这个）
CALIB = [
    (94,  '猎狗pro 1', '出现影子',        {'type': ('spawn',), 'tgt': '猎狗pro'}),
    (207, '芬',        '进入攻击前摇',    {'type': ('windup',), 'name': '芬'}),
    (221, '猎狗pro 1', '芬 命中',         {'type': ('damage', 'damage_first'), 'src': '芬'}),
    (236, '猎狗pro 1', '芬 阻挡',         {'type': ('block',), 'name': ('猎狗pro', '猎狗')}),
    (253, '猎狗pro 1', '芬命中',          {'type': ('damage', 'damage_first'), 'src': '芬'}),
    (255, '芬',        '猎狗pro 1 命中',  {'type': ('damage', 'damage_first'), 'src': '猎狗pro'}),
    (285, '猎狗pro 1', '芬 命中',         {'type': ('damage', 'damage_first'), 'src': '芬'}),
    (298, '芬',        '猎狗pro 1 命中',  {'type': ('damage', 'damage_first'), 'src': '猎狗pro'}),
    (317, '猎狗pro 1', '芬 命中',         {'type': ('damage', 'damage_first'), 'src': '芬'}),
    (340, '芬',        '猎狗pro 1 命中',  {'type': ('damage', 'damage_first'), 'src': '猎狗pro'}),
    (349, '猎狗pro 1', '芬 命中',         {'type': ('damage', 'damage_first'), 'src': '芬'}),
    (367, '猎狗pro 2', '出现影子',        {'type': ('spawn',), 'tgt': ('猎狗pro', '猎狗')}),
    (381, '猎狗pro 1', '芬 击杀',         {'type': ('kill',), 'by': '芬'}),
    (432, '猎狗pro 2', '芬 命中',         {'type': ('damage', 'damage_first'), 'src': '芬'}),
    (438, '猎狗pro 2', '月见夜 远程命中', {'type': ('damage', 'damage_first'), 'src': '月见夜'}),
    (443, '猎狗pro 2', '芬 阻挡',         {'type': ('block',), 'name': ('猎狗pro', '猎狗')}),
    (461, '芬',        '猎狗pro 2 命中',  {'type': ('damage', 'damage_first'), 'src': '猎狗'}),
    (464, '猎狗pro 2', '芬 击杀',         {'type': ('kill',), 'by': '芬'}),
]


def match_events(ev: list[dict], pred: dict) -> list[int]:
    """按谓词筛事件帧号（带攻守/击杀者限定）。"""
    out = []
    for e in ev:
        if e['type'] not in pred['type']:
            continue
        if 'name' in pred:
            want = pred['name'] if isinstance(pred['name'], (tuple, list)) else (pred['name'],)
            if (e.get('name') or '') not in want:
                continue
        if 'src' in pred:
            want = pred['src'] if isinstance(pred['src'], (tuple, list)) else (pred['src'],)
            if (e.get('src') or '') not in want:
                continue
        if 'tgt' in pred:
            want = pred['tgt'] if isinstance(pred['tgt'], (tuple, list)) else (pred['tgt'],)
            if (e.get('name') or '') not in want:
                continue
        if 'by' in pred:
            det = e.get('detail') or {}
            if det.get('by') != pred['by']:
                continue
        out.append(e['frame'])
    return out



def to_rc(tile: str):
    return ord(tile[0].upper()) - 65, int(tile[1:]) - 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', default=None)
    ap.add_argument('--max-frames', type=int, default=600)
    a = ap.parse_args()
    if a.mode:
        os.environ['AK_SIM_TIME_MODE'] = a.mode

    from ak_sim import timeline
    print(f'=== 模拟环境 vs 1-1 标定 ===  时间口径 TIME_MODE = {timeline.TIME_MODE}')
    t0 = time.time()
    sc = Scenario(STAGE)
    b = Battle(sc.stage_code, seed=0, record=True, record_every=1, max_frames=a.max_frames)
    plan = {}
    for f, ch, tile, d, cov in DEPLOYS:
        plan.setdefault(f, []).append((ch, to_rc(tile), d, cov))

    dep_ok = []
    for f in range(a.max_frames):
        b.tick()
        if b.frame in plan:
            for ch, rc, d, cov in plan[b.frame]:
                u = b.deploy(ch, rc[0], rc[1], direction=DIR_MAP[d], elite=2, level=90,
                             potential=6, trust=200, skill_index=0, skill_level=7, cost=cov)
                dep_ok.append((b.frame, ch, rc, d, bool(u), b.cost))
    dt = time.time() - t0

    print('\n§1 部署对齐')
    for f, ch, rc, d, ok, cost in dep_ok:
        print(f'  标定帧 {f:>4}：{ch} @{rc} 朝{d} ⇒ {"成功" if ok else "★失败"}，费用={cost:.1f}'
              f'（轴表口径：帧 {f}）')

    ev = extract_events(b.frames)
    print(f'\n§2 逐事件对照（模拟器事件共 {len(ev)} 条；耗时 {dt:.3f}s ≈ '
          f'{(b.frame/30)/dt:.1f}× 实时）')
    print(f'  {"标定帧":>6} {"单位":<10} {"描述":<16} {"模拟器最近同类":>14} {"Δ帧":>5}')
    deltas, misses, na = [], [], []
    for f, unit, desc, pred in CALIB:
        if False:
            print(f'  {f:>6} {unit:<10} {desc:<16} {"（模拟器未发该事件）":>14} {"—":>5}')
            na.append((f, unit, desc))
            continue
        cands = match_events(ev, pred)
        if not cands:
            print(f'  {f:>6} {unit:<10} {desc:<16} {"（无同类事件）":>14} {"—":>5}')
            misses.append((f, unit, desc))
            continue
        near = min(cands, key=lambda x: abs(x - f))
        d = near - f
        deltas.append(abs(d))
        print(f'  {f:>6} {unit:<10} {desc:<16} {near:>14} {d:>+5}')
    clean = [x for x in deltas if x <= 10]
    print(f'\n§3 汇总：可对照 {len(deltas)}/{len(CALIB)} 条（{len(na)} 条模拟器无对应事件）')
    print(f'   · **口径相符子集（|Δ|≤10 帧）**：{len(clean)} 条 ⇒ '
          f'平均 |Δ| **{sum(clean)/max(1,len(clean)):.2f} 帧**、最大 **{max(clean or [0])} 帧**；'
          f'完全命中 {sum(1 for x in clean if x == 0)}、≤2 帧 {sum(1 for x in clean if x <= 2)}、'
          f'≤4 帧 {sum(1 for x in clean if x <= 4)}')
    print(f'   · 全部可比条目（含口径差异）：平均 {sum(deltas)/max(1,len(deltas)):.2f} 帧、最大 {max(deltas or [0])} 帧')
    if misses:
        print(f'  无同类事件：{misses}')
    if na:
        print(f'  模拟器未实现的事件：{na}')

    out = os.path.join(r'C:\Users\23922\Documents\ds_harness\ak\.tmp', 't200_align_report.json')
    json.dump({'time_mode': timeline.TIME_MODE, 'deploys': dep_ok,
               'events': ev, 'calib': [list(x[:3]) for x in CALIB],
               'deltas': deltas, 'misses': misses},
              open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'\n明细已写 {out}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
