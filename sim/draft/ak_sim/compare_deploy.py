# -*- coding: utf-8 -*-
"""compare_deploy.py — **实机 ↔ 模拟器：部署事件帧对照**

## 背景（实机数据，1-1 演习，2026-09-15 实测成功案例）
| 项 | 实机读数 |
|---|---|
| 部署前 | **cost = 15、fill_px = 131、tick = 21** |
| 部署后 | **cost = 8**（**恰好扣 7**，即该卡片费用） |
| 同时 | 底部第一张卡片消失、「剩余可放置角色」8 → 7 |

由费用尺口径（费用条每满一次 = 30 帧、初始费用 10）可把实机时刻换算成**游戏内帧**：
    frame ≈ (cost - initial_cost) × 30 + tick = (15 - 10) × 30 + 21 = **171**

本脚本让**模拟器**在同一条时间轴上做同样的部署，输出它能给出的事件帧，
与实机对照（用户口径：**以事件发生的精确帧判定准确性**）。

## 用法
    python ak_sim/compare_deploy.py [--realtime-frame 171] [--cost 7]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim.engine import Battle              # noqa: E402
from ak_sim.events import extract_events      # noqa: E402
from ak_sim.scenario import Scenario          # noqa: E402

# 实机观测（1-1 演习）
REAL = {'stage': '1-1', 'cost_before': 15, 'tick_before': 21, 'cost_after': 8,
        'card_cost': 7, 'placeable_before': 8, 'placeable_after': 7}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--realtime-frame', type=int, default=171,
                    help='实机部署时刻换算出的游戏内帧（默认按 (15-10)*30+21=171）')
    ap.add_argument('--cost', type=int, default=7, help='部署干员的费用（实机扣了 7）')
    ap.add_argument('--char', default='char_123_fang', help='模拟器用的干员 id（芬，7 费先锋）')
    a = ap.parse_args()

    sc = Scenario(REAL['stage'])
    b = Battle(sc.stage_code, seed=0, record=True, record_every=1, max_frames=1200)
    print(f"=== 实机 ↔ 模拟器 部署对照（{REAL['stage']} {sc.stage_code}）===")
    print(f"实机：部署前 cost={REAL['cost_before']} tick={REAL['tick_before']} ⇒ "
          f"换算游戏内帧 ≈ {a.realtime_frame}；部署后 cost={REAL['cost_after']}（扣 {REAL['card_cost']}）")

    deployed_at = None
    cost_at_deploy = None
    tick_at_deploy = None
    for f in range(1200):
        b.tick()
        # ★ 与实机**同一判据**：实机是在 cost=15 且 tick=21 时部署的
        #   （tick = 该秒内的帧位置 = frame % 30），因此等到 tick 也对上再部署。
        if deployed_at is None and b.cost >= REAL['cost_before'] and (b.frame % 30) >= REAL['tick_before']:
            deployed_at = b.frame
            cost_at_deploy = b.cost
            tick_at_deploy = b.frame % 30
            u = b.deploy(a.char, 3, 4, direction='右', elite=2, level=90, potential=6,
                         trust=200, skill_index=0, skill_level=7, cost=a.cost)
            print(f"模拟器：在第 {deployed_at} 帧部署（cost={cost_at_deploy}、"
                  f"tick={tick_at_deploy}）、费用扣至 {b.cost}；部署返回 {'成功' if u else '失败'}")
        if deployed_at and b.frame > deployed_at + 90:
            break

    # 模拟器事件时间线（取 deploy 附近）
    ev = extract_events(b.frames)
    near = [e for e in ev if abs(e['frame'] - (deployed_at or 0)) <= 60]
    print('\n模拟器事件时间线（部署帧 ±60 内）：')
    for e in near[:14]:
        print('   ', json.dumps(e, ensure_ascii=False)[:140])

    # 对照表
    print('\n=== 对照结论 ===')
    print(f"  实机：部署前费用 {REAL['cost_before']} → 后 {REAL['cost_after']}（Δ = "
          f"{REAL['cost_after'] - REAL['cost_before']}）")
    cost_near = [e for e in near if e['type'] in ('cost_spend', 'cost_up')]
    spend = [e for e in cost_near if e['type'] == 'cost_spend']
    if spend:
        print(f"  模拟器：部署帧 {deployed_at} 发生 cost_spend Δ = {spend[0]['delta']}")
        print(f"  ⇒ 费用变化一致性：实机 Δ={REAL['cost_after']-REAL['cost_before']} vs "
              f"模拟器 Δ={spend[0]['delta']} ⇒ "
              f"{'一致 ✓' if abs(spend[0]['delta'] - (REAL['cost_after']-REAL['cost_before'])) < 0.01 else '不一致 ✗'}")
    print(f"\n  实机时刻（游戏内帧）≈ {a.realtime_frame}；模拟器部署帧 = {deployed_at}"
          f"（差异 {None if deployed_at is None else abs(deployed_at - a.realtime_frame)} 帧）")
    print('  说明：实机帧由「费用+相位」换算，模拟器帧由逐帧切片给出，两者同一时间轴。')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
