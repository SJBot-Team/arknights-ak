# -*- coding: utf-8 -*-
"""probe_en2_route.py — 核对"第 2 只猎狗是否进入芬的攻击范围"+"影子 vs spawn"语义

## 背景（上一轮残余）
- 标定「帧 432 芬 命中 猎狗」+「帧 464 芬 击杀 猎狗」⇒ 实机中**芬参与了击杀第 2 只**；
- 但模拟器中**第 2 只（`enemy_1000_gopro`, hp820）只被月见夜打**（569+251=820，正好打死）
  ⇒ 芬完全没打它。
⇒ 需核：**第 2 只的路线（routeIndex=4）是否经过芬（D6 = row3,col5）**；
   若实机经过而模拟器不经过，则是**路线/寻路/速度**问题。

另外核对 **"出现影子" 与 `spawn` 的语义差**（标定 367 vs 模拟器 360，−7 帧）。

## 本脚本输出
1. 第 2 只猎狗的路线（route 4）的检查点坐标序列；
2. 芬的位置与其**阻挡半径/攻击范围**；
3. 逐帧打印"第 2 只"与芬的格距，找出最接近的时刻；
4. 对照标定：帧 432 / 464 时该敌人的位置应已在芬身边。
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim import data as D            # noqa: E402
from ak_sim.engine import Battle        # noqa: E402
from ak_sim.scenario import Scenario    # noqa: E402

STAGE = '1-1'
FANG, MIDN = 'char_123_fang', 'char_283_midn'
DIR_MAP = {'左': '左', '上': '上'}
DEPLOYS = [(10, FANG, 'D6', '左', 8), (411, MIDN, 'D4', '上', None)]


def to_rc(tile):
    return ord(tile[0]) - 65, int(tile[1:]) - 1


def main():
    sc = Scenario(STAGE)
    lv = D.load_level(sc.stage_code)
    print('=== 一、关卡 routes（前 6 条）===')
    routes = lv.get('routes') or []
    for i, r in enumerate(routes[:6]):
        cps = r.get('checkpoints') or []
        print(f'  route{i}: {len(cps)} 检查点；前几个: '
              f'{[(c.get("type"), round(c.get("position", {}).get("row", -1), 2), round(c.get("position", {}).get("col", -1), 2)) for c in cps[:4]]}')

    print('\n=== 二、复刻并逐帧追踪"第 2 只"（route4）与芬的关系 ===')
    b = Battle(sc.stage_code, seed=0, record=True, record_every=1, max_frames=700)
    plan = {}
    for f, char, tile, direc, cov in DEPLOYS:
        plan.setdefault(f, []).append((char, to_rc(tile), direc, cov))
    for f in range(700):
        b.tick()
        if b.frame in plan:
            for char, (r, c), direc, cov in plan[b.frame]:
                b.deploy(char, r, c, direction=DIR_MAP[direc], elite=2, level=90,
                         potential=6, trust=200, skill_index=0, skill_level=7, cost=cov)

    fang = next((u for u in b.units.values() if u.name == '芬'), None)
    if fang is None:
        print('  ★未找到芬')
        return
    print(f'  芬: pos=({fang.x},{fang.y}) block_cnt={fang.block_cnt} range_id={getattr(fang, "range_id", None)}')

    # 找"第 2 只"（uid 为第 2 个敌方 spawn 的 uid）
    spawns = []
    for fr in b.frames:
        for u in (fr.get('units') or []):
            if u.get('is_operator'):
                continue
            if u.get('uid') not in [s[0] for s in spawns]:
                spawns.append((u['uid'], u.get('name'), fr['f']))
    spawns.sort(key=lambda z: z[2])
    print(f'  敌方出现: {spawns}')
    if len(spawns) < 2:
        print('  ★不足两只')
        return
    en2_uid = spawns[1][0]

    print(f'\n  逐帧追踪 第2只(uid={en2_uid}) 与芬的格距（打印变化点）:')
    prev = None
    for fr in b.frames:
        if fr['f'] < 350 or fr['f'] > 560:
            continue
        for u in (fr.get('units') or []):
            if u.get('uid') != en2_uid:
                continue
            try:
                d = ((float(u['x']) - float(fang.x)) ** 2 + (float(u['y']) - float(fang.y)) ** 2) ** 0.5
            except Exception:
                continue
            key = (round(d, 1), u.get('state'), u.get('hp'))
            if key != prev:
                near = '  ← 进入近战范围(≤1.5)' if d <= 1.5 else ''
                print(f'    帧 {fr["f"]:>4}: 第2只 pos=({u["x"]:.2f},{u["y"]:.2f}) '
                      f'状态={u.get("state")} hp={u.get("hp")} 距芬={d:.2f}{near}')
                prev = key

    print('\n=== 三、对照 ===')
    print('  标定：帧 432「芬 命中 猎狗」 ⇒ 该时刻第 2 只应在芬的近战范围内')
    print('  标定：帧 464「芬 击杀 猎狗」')


if __name__ == '__main__':
    main()
