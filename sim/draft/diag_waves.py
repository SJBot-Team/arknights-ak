# -*- coding: utf-8 -*-
"""diag_waves.py — 打印波次原始结构与两种时间语义下的出怪时刻，核对「是否整体偏早 ~7s」。

背景：实机锚定测量给出首漏 ≈44.3s，模拟器 37.3s —— 三只进点时刻整体只差 +7s 的**均匀平移**
（37.3/39.8/43.7 → 44.3/46.8/50.7 vs 实机 44.3/46.0/51.5），
这更像**波次时间表整体早 7s**，而不是「移动速度偏快」。
本脚本把 waves 的 preDelay 结构摊开，并对比两种语义：
  A) 逐片段累加（现实现，与 parse_level_spawns 一致）
  B) 片段 preDelay 相对所在波次起点
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim import scenario_h124 as S                  # noqa: E402
from ak_sim.engine import Battle, build_schedule       # noqa: E402

FPS = 30


def main():
    b = Battle(S.LEVEL, seed=0, record=False)
    waves = b.level.get('waves') or []
    print(f'波次 {len(waves)} 个')
    for wi, w in enumerate(waves[:4]):
        print(f'\n=== wave {wi}  preDelay={w.get("preDelay")}  fragments={len(w.get("fragments") or [])} ===')
        for fi, fr in enumerate(w.get('fragments') or []):
            acts = fr.get('actions') or []
            print(f'  frag {fi} preDelay={fr.get("preDelay")} actions={len(acts)}')
            for a in acts[:4]:
                print(f'      {a.get("actionType")} key={a.get("key")} route={a.get("routeIndex")} '
                      f'count={a.get("count")} preDelay={a.get("preDelay")} interval={a.get("interval")}')

    sched = build_schedule(b.level)
    sp = [a for a in sched if a['type'] == 'SPAWN']
    print(f'\n=== 现实现（语义 A：逐片段累加）前 12 个出怪 ===')
    for a in sp[:12]:
        print(f'  t={a["t"]:6.1f}s wave={a["wave"]} frag={a["frag"]} {a["key"]:<24} route={a["route"]}')
    print(f'  最晚出怪 t={sp[-1]["t"]:.1f}s；共 {len(sp)} 只')

    # 语义 B：片段 preDelay 相对波次起点
    alt = []
    for wi, w in enumerate(waves):
        if not w.get('fragments'):
            continue
        base = float(w.get('preDelay') or 0.0)
        for fi, fr in enumerate(w.get('fragments') or []):
            ft = base + float(fr.get('preDelay') or 0.0)
            for a in fr.get('actions') or []:
                for c in range(int(a.get('count', 1))):
                    alt.append((ft + float(a.get('preDelay') or 0.0) + float(a.get('interval') or 0.0) * c,
                                a.get('key')))
    alt.sort()
    print(f'\n=== 语义 B（片段 preDelay 相对波次起点）前 12 个出怪 ===')
    for t, k in alt[:12]:
        print(f'  t={t:6.1f}s {k}')
    if alt:
        print(f'  最晚出怪 t={alt[-1][0]:.1f}s；共 {len(alt)} 只')


if __name__ == '__main__':
    main()
