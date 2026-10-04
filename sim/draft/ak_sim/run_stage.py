# -*- coding: utf-8 -*-
"""run_stage.py — **通用关卡试跑入口**：空轴基线跑 + 事件时间线输出

## 用途
1. **验证模拟器支持任意关卡**（配合 `scenario.py` 的关卡驱动加载）；
2. 产出**空轴基线事件时间线**（出怪 / 漏怪 / 生命变化 / 费用变化），
   作为后续"与实机/视频事件帧比对"的**定位基准**（用户要求：预置验证定位）；
3. 顺带检验**随机数可控**（同一 seed 两次运行事件应完全一致；换 seed 应有差异）。

用法：
    python ak_sim/run_stage.py 1-1                 # 空轴跑到结束
    python ak_sim/run_stage.py 1-7 --seed 123 --json out.json
    python ak_sim/run_stage.py 1-1 --repeat 2      # 同 seed 跑两次比对（随机数可控性自检）
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim.engine import Battle              # noqa: E402
from ak_sim.scenario import Scenario          # noqa: E402


def run_once(stage: str, seed: int, max_frames: int, verbose: bool):
    sc = Scenario(stage)
    b = Battle(sc.stage_code, seed=seed, record=True, record_every=1, max_frames=max_frames)
    events = []
    life0 = None
    leak_times = []
    prev_life = None
    f = 0
    while f < max_frames:
        b.tick()
        f += 1
        life = getattr(b, 'life', None)
        if life is None:
            life = getattr(b, 'life_point', None)
        if life0 is None and life is not None:
            life0 = life
            prev_life = life
        if prev_life is not None and life is not None and life != prev_life:
            leak_times.append(round(f / 30.0, 2))
            events.append({'frame': f, 't': round(f / 30.0, 2), 'type': 'life_change',
                           'from': prev_life, 'to': life})
            prev_life = life
        if life is not None and life <= 0:
            events.append({'frame': f, 't': round(f / 30.0, 2), 'type': 'defeat'})
            break
    alive = len(getattr(b, 'enemies', []) or [])
    return {'stage': stage, 'stage_code': sc.stage_code, 'seed': seed,
            'frames': f, 'seconds': round(f / 30.0, 2),
            'life0': life0, 'life_end': prev_life, 'leaks': leak_times,
            'enemies_alive': alive, 'events': events}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('stage')
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--max-frames', type=int, default=18000)
    ap.add_argument('--json', default=None)
    ap.add_argument('--repeat', type=int, default=1)
    ap.add_argument('--verbose', action='store_true')
    a = ap.parse_args()

    r = run_once(a.stage, a.seed, a.max_frames, a.verbose)
    print(f'=== 空轴基线：{a.stage}  ({r["stage_code"]})  seed={a.seed} ===')
    print(f'  跑 {r["frames"]} 帧 = {r["seconds"]}s   初始生命={r["life0"]}  结束生命={r["life_end"]}')
    print(f'  漏怪时刻（生命变化）: {r["leaks"]}')
    print(f'  存活敌人 {r["enemies_alive"]}')
    if a.verbose:
        for e in r['events'][:20]:
            print('   ', e)

    if a.repeat >= 2:
        print(f'\n=== 随机数可控性自检（同 seed 跑 {a.repeat} 次）===')
        sig = (tuple(r['leaks']), r['frames'], r['life_end'])
        same = True
        for i in range(2, a.repeat + 1):
            r2 = run_once(a.stage, a.seed, a.max_frames, False)
            sig2 = (tuple(r2['leaks']), r2['frames'], r2['life_end'])
            eq = (sig == sig2)
            same &= eq
            print(f'  第{i}次: 漏怪{sig2[0]} 帧数{sig2[1]} 结束生命{sig2[2]} ⇒ {"一致" if eq else "★不一致"}')
        print(f'  ⇒ 同 seed 结果{"完全一致 ✓（随机数可控）" if same else "不一致 ✗（需排查）"}')
        r3 = run_once(a.stage, a.seed + 1, a.max_frames, False)
        print(f'  换 seed(+1): 漏怪{tuple(r3["leaks"])} 帧数{r3["frames"]} ⇒ '
              f'{"有差异（随机性生效）" if (tuple(r3["leaks"]), r3["frames"]) != sig[:2] else "无差异（本关可能无随机点）"}')

    if a.json:
        json.dump(r, open(a.json, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(f'\n已写 {a.json}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
