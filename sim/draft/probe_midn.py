# -*- coding: utf-8 -*-
"""probe_midn.py — 查月见夜的攻击明细与 EN2 的伤害分配（帧438 +40 的来源）

## 背景（上一轮残余）
- 标定：帧 438「猎狗pro 2 ｜ 月见夜 远程命中」
- 模拟器：该条被配到 EN2 的第 2 次伤害（帧 478）⇒ 偏差 +40
⇒ 需查：**月见夜在模拟器里到底打了谁、何时打、弹道时序如何**；
   以及 EN2（敌方第 2 只 = `enemy_1000_gopro`，hp820）的伤害是否被"芬"独占。

## 本脚本输出
1. 月见夜的攻击/伤害事件明细（帧、目标、伤害）；
2. EN2 的全部伤害事件及其来源（芬 / 月见夜）；
3. 芬与月见夜各自的攻击周期（间隔）统计。
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim.engine import Battle              # noqa: E402
from ak_sim.events import extract_events      # noqa: E402
from ak_sim.scenario import Scenario          # noqa: E402

STAGE = '1-1'
FANG, MIDN = 'char_123_fang', 'char_283_midn'
ALLY_NAMES = ('芬', '月见夜')
DIR_MAP = {'左': '左', '上': '上'}
DEPLOYS = [(10, FANG, 'D6', '左', 8), (411, MIDN, 'D4', '上', None)]


def to_rc(tile):
    return ord(tile[0]) - 65, int(tile[1:]) - 1


def main():
    sc = Scenario(STAGE)
    b = Battle(sc.stage_code, seed=0, record=True, record_every=1, max_frames=700)
    plan = {}
    for f, char, tile, direc, cov in DEPLOYS:
        plan.setdefault(f, []).append((char, to_rc(tile), direc, cov))
    for f in range(700):
        b.tick()
        if b.frame in plan:
            for char, (r, c), direc, cov in plan[b.frame]:
                u = b.deploy(char, r, c, direction=DIR_MAP[direc], elite=2, level=90,
                             potential=6, trust=200, skill_index=0, skill_level=7, cost=cov)
                print(f'部署 {char} @({r},{c}) 帧={b.frame} ⇒ {"成功" if u else "失败"}')

    ev = extract_events(b.frames)
    order, n = {}, 0
    for e in sorted((x for x in ev if x['type'] == 'spawn'), key=lambda z: z['frame']):
        if any(a in str(e.get('name') or '') for a in ALLY_NAMES):
            continue
        n += 1
        order[e.get('uid')] = n
    print(f'\n敌方出现顺序（uid→序号）: {order}')

    print('\n=== 一、全部伤害事件（按来源/目标分类）===')
    print(f'{"帧":>5} {"类型":>13} {"受害者":>10} {"uid":>4} {"敌序":>5} {"伤害":>6}')
    for e in ev:
        if e['type'] not in ('damage', 'damage_first'):
            continue
        nm = str(e.get('name') or '')
        is_ally = any(a in nm for a in ALLY_NAMES)
        print(f'{e["frame"]:>5} {e["type"]:>13} {nm:>10} {e.get("uid"):>4} '
              f'{("ALLY" if is_ally else order.get(e.get("uid"), "?")):>5} {e.get("dmg"):>6}')

    print('\n=== 二、EN2 的伤害事件（敌方第 2 只：enemy_1000_gopro, hp820）===')
    e2 = [e for e in ev if e['type'] in ('damage', 'damage_first')
          and order.get(e.get('uid')) == 2]
    for e in e2:
        print(f'  帧 {e["frame"]:>4}: 受 {e["dmg"]:>4} 伤害 → hp {e.get("hp")}（hp_before {e.get("hp_before")}）')
    if e2:
        gaps = [b2['frame'] - a['frame'] for a, b2 in zip(e2, e2[1:])]
        print(f'  间隔: {gaps}')

    print('\n=== 三、我方各单位的攻击间隔（由"敌受伤"事件推）===')
    for uid, u in sorted(b.units.items()):
        if u.side != 'ALLY':
            continue
        print(f'  {u.name}: atk_interval_frames={u.attack_interval_frames} '
              f'range_id={getattr(u, "range_id", None)} x={u.x} y={u.y}')

    print('\n=== 四、克洛丝/月见夜是否进入了攻击状态 ===')
    from collections import Counter
    c = Counter()
    for fr in b.frames:
        for un in (fr.get('units') or []):
            if un.get('name') == '月见夜':
                c[un.get('state')] += 1
    print(f'  月见夜的 state 分布: {dict(c)}')

    print('\n=== 五、与标定对照 ===')
    print('  标定：帧 438 月见夜 远程命中（猎狗pro 2）')
    print('  模拟器 EN2 的伤害事件如上；若全为"芬"所打，则标定的"月见夜远程命中"应是另一目标。')


if __name__ == '__main__':
    main()
