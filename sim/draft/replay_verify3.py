# -*- coding: utf-8 -*-
"""replay_verify3.py — ★按"出现序号 + 阵营"配对（解决同名不同模板的混淆）

## 为什么
1-1 的猎狗有两个模板：`enemy_1000_gopro`（**猎狗**，hp820）与 `enemy_1000_gopro_2`（**猎狗pro**，hp1700），
**名字都含"猎狗"** ⇒ 按名字匹配会把两者混在一起（导致后 5 条偏差 26~58 帧）。

标定表用「猎狗pro 1 / 猎狗pro 2」区分，实测对应：
- 帧 94（影子）⇒ 模拟器帧 90 的 `gopro_2`（第 1 只猎狗类）
- 帧 367（影子）⇒ 模拟器帧 360 的 `gopro`（第 2 只猎狗类）
⇒ 标定的 1/2 是「**猎狗类敌人的出现序号**」而非模板差异。

## 配对规则
1. 模拟器：按 **spawn 帧** 给每个敌人实例编"出现序号"（分阵营）；
2. 标定：把"猎狗pro N"解析为"敌方第 N 只"；我方单位（芬/月见夜）按名字归入 ALLY 组；
3. 组内**按序号配对**（第 n 个标定事件 ↔ 第 n 个模拟器事件）。
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim.engine import Battle              # noqa: E402
from ak_sim.events import extract_events      # noqa: E402
from ak_sim.scenario import Scenario          # noqa: E402

STAGE = '1-1'
FANG, MIDN = 'char_123_fang', 'char_283_midn'
ALLY_NAMES = ('芬', '月见夜', '令', '蕾缪安')
DIR_MAP = {'左': '左', '右': '右', '上': '上', '下': '下'}
DEPLOYS = [(10, FANG, 'D6', '左', 8), (411, MIDN, 'D4', '上', None)]

# 标定：帧, 受害者描述, 动画层
CALIB = [
    (94, '猎狗pro 1', '出现影子'), (207, '芬', '进入攻击前摇'), (221, '猎狗pro 1', '芬 命中'),
    (236, '猎狗pro 1', '芬 阻挡'), (253, '猎狗pro 1', '芬命中'), (255, '芬', '猎狗pro 1 命中'),
    (285, '猎狗pro 1', '芬 命中'), (298, '芬', '猎狗pro 1 命中'), (317, '猎狗pro 1', '芬 命中'),
    (340, '芬', '猎狗pro 1 命中'), (349, '猎狗pro 1', '芬 命中'), (367, '猎狗pro 2', '出现影子'),
    (381, '猎狗pro 1', '芬 击杀'), (432, '猎狗pro 2', '芬 命中'),
    (438, '猎狗pro 2', '月见夜 远程命中'), (443, '猎狗pro 2', '芬 阻挡'),
    (461, '芬', '猎狗pro 2 命中'), (464, '猎狗pro 2', '芬 击杀'),
]
KIND_MAP = {'出现影子': 'spawn', '进入攻击前摇': 'hit', '命中': 'hit',
            '阻挡': 'hit', '击杀': 'kill'}


def classify(desc):
    for k, v in KIND_MAP.items():
        if k in desc:
            return v
    return '?'


def side_of(desc: str):
    """由标定的"受害者描述"判断阵营与其在敌方中的序号。"""
    if any(a in desc for a in ALLY_NAMES):
        return 'ALLY', None
    m = re.search(r'(\d+)', desc)
    return 'ENEMY', (int(m.group(1)) if m else 1)


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
                b.deploy(char, r, c, direction=DIR_MAP[direc], elite=2, level=90,
                         potential=6, trust=200, skill_index=0, skill_level=7, cost=cov)

    ev = extract_events(b.frames)
    # ① 给**敌方**实例编"出现序号"（★必须排除我方干员的 spawn：部署干员同样会产生 spawn 事件，
    #    否则序号会被干员占位，导致"猎狗pro 1/2"与模拟器实例错配）
    order = {}
    n = 0
    for e in sorted((x for x in ev if x['type'] == 'spawn'), key=lambda z: z['frame']):
        nm = str(e.get('name') or '')
        if any(a in nm for a in ALLY_NAMES):
            continue                     # 我方干员不计入敌方序号
        n += 1
        order[e.get('uid')] = n
    sp = {e.get('uid'): e for e in ev if e['type'] == 'spawn'}
    print('敌方出现顺序:')
    for uid, idx in sorted(order.items(), key=lambda kv: kv[1]):
        e = sp[uid]
        print(f'  第{idx}只: uid={uid} key={e.get("key")} name={e.get("name")} 帧={e["frame"]}')

    # ② 模拟器事件分组： ('hit'|'kill'|'spawn', 阵营, 序号)
    sim = {}
    for e in ev:
        t = e['type']
        if t == 'spawn':
            key = ('spawn', 'ENEMY', order.get(e.get('uid'), 1))
        elif t in ('damage', 'damage_first'):
            nm = str(e.get('name') or '')
            if any(a in nm for a in ALLY_NAMES):
                key = ('hit', 'ALLY', None)
            else:
                key = ('hit', 'ENEMY', order.get(e.get('uid'), 1))
        elif t in ('despawn', 'kill'):
            nm = str(e.get('name') or '')
            key = (('kill', 'ALLY', None) if any(a in nm for a in ALLY_NAMES)
                   else ('kill', 'ENEMY', order.get(e.get('uid'), 1)))
        else:
            continue
        sim.setdefault(key, []).append(e['frame'])
    for k in sim:
        sim[k].sort()

    # ③ 标定分组
    cal = {}
    for f, unit, desc in CALIB:
        cat = classify(desc)
        sd, idx = side_of(unit)
        cal.setdefault((cat, sd, idx), []).append((f, unit, desc))
    for k in cal:
        cal[k].sort()

    print(f'\n{"标定帧":>6} {"受害者":>10} {"类别":>6} {"阵营":>6} {"#":>3} {"动画层":>16} '
          f'{"模拟器帧":>9} {"偏差":>6}')
    print('-' * 82)
    diffs = []
    for k in sorted(cal.keys(), key=lambda z: cal[z][0][0]):
        cat, sd, idx = k
        sims = sim.get(k, [])
        if not sims:
            # 回退：同类别同阵营的全集（按序号）
            cand = sim.get((cat, sd, None))
            if cand:
                sims = cand
        for i, (f, unit, desc) in enumerate(cal[k]):
            if i < len(sims):
                ef = sims[i]
                d = abs(ef - f)
                diffs.append(d)
                print(f'{f:>6} {unit:>10} {cat:>6} {sd:>6} {i:>3} {desc:>16} {ef:>9} {ef - f:>+6}'
                      + ('  OK' if d <= 6 else '  ★偏大'))
            else:
                print(f'{f:>6} {unit:>10} {cat:>6} {sd:>6} {i:>3} {desc:>16} {"(缺)":>9} {"-":>6}')
    print('-' * 82)
    if diffs:
        hit = sum(1 for d in diffs if d <= 6)
        print(f'可对齐 {len(diffs)}/{len(CALIB)}；**|偏差|≤6 帧 {hit} 条**；'
              f'平均 {sum(diffs)/len(diffs):.2f} 帧；最大 {max(diffs)} 帧')
        print('偏差分布: ' + ', '.join(str(d) for d in sorted(diffs)))


if __name__ == '__main__':
    main()
