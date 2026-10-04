# -*- coding: utf-8 -*-
"""T-200h 探针 2：只打事件 + 关键量测（出生→阻挡→前摇→命中），并做 A/B。

只读运行模拟器（纯 Python）。
"""
from __future__ import annotations
import os
import sys

sys.path.insert(0, r'C:\Users\23922\Documents\ds_harness\ak\sim\draft')
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim.engine import Battle                      # noqa: E402
from ak_sim.scenario import Scenario                  # noqa: E402

STAGE = '1-1'
FANG = 'char_123_fang'


def run(max_frames=520, sched_off=None, extra_opts=None):
    if sched_off is not None:
        os.environ['AK_SIM_SCHED_OFFSET_FRAMES'] = str(sched_off)
    import importlib
    import ak_sim.engine as E
    importlib.reload(E)
    opts = dict(extra_opts or {})
    sc = Scenario(STAGE)
    b = E.Battle(sc.stage_code, seed=0, record=True, record_every=1,
                 max_frames=max_frames, options=opts)
    b.tick()
    b.deploy(FANG, 3, 5, direction='左', elite=2, level=90, potential=6,
             trust=200, skill_index=0, skill_level=7, cost=8)
    for _ in range(max_frames - 1):
        b.tick()
    return b


KEEP = {'spawn', 'block', 'block_offset', 'target_select', 'windup',
        'hit', 'projectile', 'kill', 'enemy_disappear'}


def dump(b, tag):
    print(f'\n===== {tag} =====')
    k0 = k1 = None
    for l in b.logs:
        if l.kind not in KEEP:
            continue
        d = l.detail or {}
        s = f'  f={l.frame:>4} {l.kind:<14}'
        if l.kind == 'spawn':
            s += f' enemy={d.get("enemy") or d.get("name")} key={d.get("key")}'
        elif l.kind == 'block':
            s += f' {d.get("enemy")} by {d.get("by")}'
        elif l.kind == 'block_offset':
            s += f' {d.get("enemy")} {d.get("from")}->{d.get("to")} dist={d.get("dist")}'
        elif l.kind == 'target_select':
            s += f' {d.get("side")} {d.get("unit")} -> {d.get("target")} judge={d.get("judge")} reach={d.get("reach")}'
        elif l.kind == 'windup':
            s += f' {d}'
        elif l.kind in ('hit', 'projectile'):
            s += f' {d.get("src")} -> {d.get("tgt")} dmg={d.get("dmg")} frames={d.get("frames")} hp_after={d.get("hp_after")}'
            if k0 is None and d.get('src') and '芬' == d.get('src'):
                k0 = l.frame
            if k1 is None and d.get('src') and '猎狗' in str(d.get('src')):
                k1 = l.frame
        elif l.kind == 'kill':
            s += f' {d}'
        else:
            s += f' {d}'
        print(s)
    print(f'  [汇总] 首次 芬命中 = {k0}, 首次 敌命中芬 = {k1}')


if __name__ == '__main__':
    off = float(sys.argv[1]) if len(sys.argv) > 1 else 0.0
    b = run(470, sched_off=off)
    dump(b, f'调度起点偏移 = {off:+.0f} 帧')
