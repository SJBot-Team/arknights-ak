# -*- coding: utf-8 -*-
"""verify_skill_cost.py — ★验证"先锋技能回费"：模拟器 vs 视频图像识别

## 背景
1-1 标定视频的费用数字在 **游戏帧 581 / 1333** 出现 **+6** 跳变（本轴由图像识别建立）。
数据层给出：芬 `skcom_charge_cost[1]`「冲锋号令·α型」技能**等级 7**：
`spCost=25 / initSp=6 / increment=1.0/s / blackboard.cost=+6`、`skillType=AUTO`。
⇒ 预测：部署帧 10 后 (25−6)=19 秒 ⇒ **帧 580**；之后每 25 秒 ⇒ **帧 1330**。

本脚本用**同一复刻**（帧10 部署芬@D6朝左 8费、帧411 部署月见夜@D4朝上）跑模拟器，
检查 `cost_recover` 事件帧与视频侧是否吻合。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim.engine import Battle              # noqa: E402
from ak_sim.scenario import Scenario          # noqa: E402

STAGE = '1-1'
FANG, MIDN = 'char_123_fang', 'char_283_midn'
DEPLOYS = [(10, FANG, 'D6', '左', 8), (411, MIDN, 'D4', '上', None)]
FRAMES = 1400

# 视频侧（图像识别）实测：费用出现 +6 跳变的游戏帧
VIDEO_SKILL_FRAMES = [581.0, 1333.0]


def to_rc(tile):
    return ord(tile[0]) - 65, int(tile[1:]) - 1


def main():
    sc = Scenario(STAGE)
    for auto in (True, False):
        b = Battle(sc.stage_code, seed=0, record=True, record_every=1, max_frames=FRAMES,
                   options={'auto_skill': auto})
        plan = {}
        for f, char, tile, direc, cov in DEPLOYS:
            plan.setdefault(f, []).append((char, to_rc(tile), direc, cov))
        cost_at = {}
        for _ in range(FRAMES):
            b.tick()
            if b.frame in plan:
                for char, (r, c), direc, cov in plan[b.frame]:
                    b.deploy(char, r, c, direction={'左': '左', '上': '上'}[direc],
                             elite=2, level=90, potential=6, trust=200,
                             skill_index=0, skill_level=7, cost=cov)
            if b.frame in (579, 580, 581, 1329, 1330, 1333):
                cost_at[b.frame] = round(b.cost, 1)

        # 自然回费：由逐帧切片的费用差分得到（引擎不写 cost_up 日志）
        cost_up = []
        prev = None
        for s in b.frames:
            if prev is not None and s['cost'] > prev:
                cost_up.append((s['f'], round(s['cost'] - prev, 1)))
            prev = s['cost']
        rec = [(l.frame, l.detail) for l in b.logs if l.kind == 'cost_recover']
        sk = [(l.frame, l.detail) for l in b.logs if l.kind == 'skill']
        print(f'\n=== auto_skill = {auto} ===')
        print(f'  自然回费(+1) {len(cost_up)} 次，前 6: {cost_up[:6]}')
        print(f'  技能发动 {len(sk)} 次: ' + ', '.join(f'帧{f}({d.get("skill")})' for f, d in sk))
        print(f'  技能回费 {len(rec)} 次: '
              + ', '.join(f'帧{f}(+{d.get("gain")}, {d.get("from")}→{d.get("to")})' for f, d in rec))
        print(f'  费用抽检: {cost_at}')
        if auto and rec:
            print('  ★ vs 视频侧（图像识别，+6 跳变）:')
            for i, (vf, (sf, d)) in enumerate(zip(VIDEO_SKILL_FRAMES, rec)):
                print(f'      第{i + 1}次  视频 {vf:.0f}  模拟器 {sf}  偏差 {sf - vf:+.0f} 帧'
                      f'  费用 {d.get("from")}→{d.get("to")}')


if __name__ == '__main__':
    main()
