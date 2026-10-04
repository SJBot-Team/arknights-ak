# -*- coding: utf-8 -*-
"""probe_cost_tick.py — 检验"费用条满一次是否严格等于 30 帧"，以及封顶/上限提升对计时的影响

## 用户 2026-09-14 的疑问
> 通常保持费用流动时费用条计时可正常使用，但本关费用不可避免会满，费用条并不严格对齐秒钟，
> 仅费用条跳动与帧数对应……由于满一次会影响"满一次=过一秒"的计时，实际会导致计时器早一秒或晚一秒，
> 需要进一步检验。

## 本脚本怎么查
模拟器在每次部署失败时都记录 `have`（当前费用）——**每帧一条**，
于是可以从日志重建**逐帧费用曲线**，进而精确回答：
  1. 费用每 +1 是否**严格间隔 30 帧**（有无累积漂移）；
  2. 封顶段（费用恒 = 上限）有多长；
  3. 上限提升（cost_cap_up）后费用**从哪一帧恢复增长**；
  4. 把"满 N 次"当作"过了 N 秒"会**累积多少误差**。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim import scenario_h124 as S            # noqa: E402
from ak_sim.axis import parse_cyberplastic        # noqa: E402
from ak_sim.engine import Battle                  # noqa: E402

FPS = 30


def main():
    ax = parse_cyberplastic(S.XLSM)
    ops = []
    for o in ax.ops:
        d = o.to_dict()
        d['char'] = S.NAME_MAP.get(o.unit, o.unit)
        d['frame'] = int(round(float(d['abs_seconds']) * FPS))
        for k, v in S.UNIT_CONFIG.get(d['char'], {}).items():
            d.setdefault(k, v)
        ops.append(d)
    ops.sort(key=lambda x: x['frame'])

    b = Battle(S.LEVEL, seed=0, record=False)
    b.run_axis(ops, name_map=S.NAME_MAP, coord_transform=S.COORD_TRANSFORM,
               max_frames=30 * 400, continue_after_fail=False,
               retry_on_cost=True, retry_on_sp=False,
               schedule=[o['frame'] for o in ops])

    # 逐帧费用曲线：来自 deploy_failed 的 have（每帧一条）
    have = {}
    for l in b.logs:
        if l.kind == 'deploy_failed' and l.detail and 'have' in l.detail:
            have[l.frame] = float(l.detail['have'])
    frames = sorted(have)
    print(f'逐帧费用样本 {len(frames)} 条，帧范围 {frames[0]}~{frames[-1]}')

    # 1) 费用 +1 的帧间隔
    print('\n=== 费用每 +1 的帧间隔（检验是否严格 30 帧）===')
    last_v, last_f = None, None
    deltas = []
    for f in frames:
        v = have[f]
        if last_v is None or v != last_v:
            if last_v is not None and v > last_v:
                d = f - last_f
                deltas.append((last_f, f, d, last_v, v))
            last_v, last_f = v, f
    for a, c, d, v0, v1 in deltas:
        flag = '' if d == 30 else f'  ★偏差 {d-30:+d} 帧'
        print(f'  帧{a:>5}({a/FPS:6.2f}s) 费用 {v0:.0f}→{v1:.0f}  间隔 {d:>3} 帧{flag}')
    if deltas:
        ds = [d for *_x, d, _a, _b in deltas]
        print(f'  ⇒ 间隔统计：min={min(ds)} max={max(ds)} 全部为30={all(d==30 for d in ds)}')

    # 2) 封顶段
    print('\n=== 封顶段（费用恒等于上限）===')
    cap_val = None
    seg_start = None
    for f in frames:
        v = have[f]
        if cap_val is None:
            cap_val, seg_start = v, f
            continue
        if v == cap_val:
            continue
        if f - seg_start > 60:      # 超过 2 秒的恒定段视为封顶
            print(f'  帧{seg_start}({seg_start/FPS:.2f}s) → 帧{f-1}({(f-1)/FPS:.2f}s)  '
                  f'恒定 {cap_val:.0f}，持续 {f-seg_start} 帧（{(f-seg_start)/FPS:.2f}s）')
        cap_val, seg_start = v, f

    # 3) 上限提升与恢复
    print('\n=== 上限提升事件（费用重新流动的锚点）===')
    for l in b.logs:
        if l.kind == 'cost_cap_up':
            print(f'  帧{l.frame}({l.frame/FPS:.2f}s) → 上限 {l.detail.get("cost_max")} '
                  f'(bonus {l.detail.get("bonus")})')

    # 4) "满 N 次 = N 秒" 的累积误差
    print('\n=== 把"费用满一次"当作"过一秒"的累积误差 ===')
    if deltas:
        # 用相邻样本累计：若把每次 +1 都算作 30 帧，与真实帧差比较
        tot_real = deltas[-1][1] - deltas[0][0]
        tot_assumed = 30 * len(deltas)
        print(f'  样本跨度：真实 {tot_real} 帧（{tot_real/FPS:.2f}s），'
              f'按"满{len(deltas)}次=N秒"折算 {tot_assumed} 帧（{tot_assumed/FPS:.2f}s）')
        print(f'  ⇒ 净误差 {tot_assumed - tot_real:+d} 帧（{(tot_assumed-tot_real)/FPS:+.2f}s）'
              f'  —— 若期间**发生过封顶**，误差会随封顶时长线性增大')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
