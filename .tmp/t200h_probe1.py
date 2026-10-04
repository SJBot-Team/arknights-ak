# -*- coding: utf-8 -*-
"""T-200h 探针 1：逐帧 trace 猎狗pro→芬 的下游链（出生 / 移动 / 阻挡 / 前摇 / 命中）。

只读运行模拟器（纯 Python），不接触 MuMu / 游戏 / D:\\YostarGames。
"""
from __future__ import annotations
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
SIM = r'C:\Users\23922\Documents\ds_harness\ak\sim\draft'
sys.path.insert(0, SIM)
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim.engine import Battle                      # noqa: E402
from ak_sim.scenario import Scenario                  # noqa: E402

STAGE = '1-1'
FANG = 'char_123_fang'


def run(max_frames=520, opts=None):
    sc = Scenario(STAGE)
    b = Battle(sc.stage_code, seed=0, record=True, record_every=1,
               max_frames=max_frames, options=opts)
    b.tick()
    b.deploy(FANG, 3, 5, direction='左', elite=2, level=90, potential=6,
             trust=200, skill_index=0, skill_level=7, cost=8)
    for _ in range(max_frames - 1):
        b.tick()
    return b


def unit_by_key(b, key):
    for u in b.units.values():
        if u.key == key or u.name == key:
            return u
    return None


def summarize(b):
    print(f'[opts] block_rule={getattr(b,"block_rule",None)} '
          f'block_radius={getattr(b,"block_radius",None)} '
          f'block_ticker_phase={getattr(b,"block_ticker_phase",None)} '
          f'move_multiplier={getattr(b,"move_multiplier",None)} '
          f'move_inertia={getattr(b,"move_inertia",None)} '
          f'straight_path={getattr(b,"straight_path",None)}')
    for u in sorted(b.units.values(), key=lambda z: z.uid):
        if not u.is_operator and 'gopro' not in (u.key or '') and 'slime' not in (u.key or ''):
            continue
        print(f'[unit] uid={u.uid} key={u.key} name={u.name} side={u.side} '
              f'grid={u.grid()} spawn_frame={getattr(u,"spawn_frame",None)} '
              f'deploy_frame={getattr(u,"deploy_frame",None)} '
              f'move_speed={u.move_speed} atk_iv={u.attack_interval_frames} '
              f'maxSteer={getattr(u,"max_steering_force",None)} '
              f'windup={b._windup_frames(u)} 源={getattr(u,"_windup_source",None)} '
              f'pre_delay_fp={getattr(u,"pre_delay_fp",None)} '
              f'_windup_ratio={getattr(u,"_windup_ratio",None)}')


def trace(b, f0, f1, want=('gopro', '芬')):
    for fr in b.frames:
        f = fr['f']
        if not (f0 <= f <= f1):
            continue
        for u in fr['units']:
            nm = u['name']
            key = u['key']
            if not any(w in (key or '') or w in (nm or '') for w in want):
                continue
            print(f'  f={f:>4} {nm:<10} key={key:<24} pos=({u["x"]:.4f},{u["y"]:.4f}) '
                  f'v=({u["vx"]:+.3f},{u["vy"]:+.3f})|{u["v_abs"]:.3f} '
                  f'{u["state"]:<8} blocked={u["blocked"]} blocking={u["blocking"]} '
                  f'atk_start_wl={u["atk_windup_left"]} cd={u["atk_cd_frames"]} hp={u["hp"]}')


if __name__ == '__main__':
    a = int(sys.argv[1]) if len(sys.argv) > 1 else 80
    z = int(sys.argv[2]) if len(sys.argv) > 2 else 280
    b = run(320)
    summarize(b)
    trace(b, a, z)
