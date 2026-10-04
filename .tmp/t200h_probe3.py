# -*- coding: utf-8 -*-
"""T-200h 探针 3：量测"周期重启"相位（验证 `el >= interval ⇒ cd=0` 的 off-by-one）。

思路：从 slice 里读 `atk_cd_frames` / `atk_windup_left`，重建每次攻击的 start 帧。
只读运行模拟器。
"""
from __future__ import annotations
import os
import sys

sys.path.insert(0, r'C:\Users\23922\Documents\ds_harness\ak\sim\draft')
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim.engine import Battle                      # noqa: E402
from ak_sim.scenario import Scenario                  # noqa: E402


def run(max_frames=520, opts=None, off=0):
    os.environ['AK_SIM_SCHED_OFFSET_FRAMES'] = str(off)
    import importlib
    import ak_sim.engine as E
    importlib.reload(E)
    sc = Scenario('1-1')
    b = E.Battle(sc.stage_code, seed=0, record=True, record_every=1,
                 max_frames=max_frames, options=opts)
    b.tick()
    b.deploy('char_123_fang', 3, 5, direction='左', elite=2, level=90, potential=6,
             trust=200, skill_index=0, skill_level=7, cost=8)
    for _ in range(max_frames - 1):
        b.tick()
    return b


def rebuild(b, want_key):
    """返回 {unit_name: [每次起手的 start 帧]} —— 由 cd 序列的"上升沿"推断。"""
    seq = {}
    for fr in b.frames:
        for u in fr['units']:
            if want_key not in (u['key'] or '') and want_key not in (u['name'] or ''):
                continue
            seq.setdefault(u['name'], []).append((fr['f'], u['atk_cd_frames'],
                                                  u['atk_windup_left']))
    out = {}
    for nm, rows in seq.items():
        starts = []
        prev_cd = 0
        for f, cd, wl in rows:
            if cd > prev_cd and (not starts or f - starts[-1] > 2):
                starts.append(f)
            prev_cd = cd
        out[nm] = starts
    return out


if __name__ == '__main__':
    for off in (0, 4):
        b = run(off=off)
        r = rebuild(b, 'fang')
        r2 = rebuild(b, 'gopro')
        print(f'\n=== 调度偏移 {off} ===')
        for nm, ss in list(r.items()) + list(r2.items()):
            if not ss:
                continue
            iv = [ss[i + 1] - ss[i] for i in range(len(ss) - 1)]
            print(f'  {nm:<10} 起手帧={ss}')
            print(f'  {"":<10} 起手间隔={iv}')
        # 直接看 cd 递减的原始序列（芬 前 60 帧）
        for fr in b.frames:
            if 200 <= fr['f'] <= 245:
                for u in fr['units']:
                    if u['key'] == 'char_123_fang':
                        print(f'    f={fr["f"]} cd={u["atk_cd_frames"]} wl={u["atk_windup_left"]}')
