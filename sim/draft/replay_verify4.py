# -*- coding: utf-8 -*-
"""replay_verify4.py — ★人工对应表 + 自动校验（得到可信的偏差基线）

## 为什么
自动配对在"同名多模板""我方/敌方同类型事件"等歧义处反复试错（已迭代 3 版未收敛）。
⇒ 改为：**人工写出"每个标定事件对应模拟器的哪个事件的第几次"**（语义已知、仅 18 条），
程序只负责**取帧、算偏差、统计**。这样既保留自动化（统计/回归），又消除配对歧义。

## 对应表的键
`(事件类别, 目标, 序号)`
- 事件类别：`spawn`（敌方出现）/ `dmg_enemy`（敌方受伤，即我方命中）/ `dmg_ally`（我方受伤）/ `kill`
- 目标：`EN1/EN2`（敌方第 1/2 只）或 `ALLY`
- 序号：**同类事件中的第 n 次**（从 0 计）

## 关键实现
先由事件流构造"**索引表**"：`{(类别,目标): [帧...]}`，再按对应表逐条取帧比较。
"""
from __future__ import annotations

import os
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

# ★人工对应表：(标定帧, 说明, 类别, 目标, 序号)
#   ★注意：「芬 阻挡」不是"伤害事件"（阻挡是接触判定），**不得编入伤害序号**，
#     否则会让后续"命中"的序号整体错位（曾造成 +32 帧的假偏差）。
#     故"阻挡"类条目以 `watch` 标记，只打印不参与偏差统计。
MAP = [
    (94,  '猎狗pro 1 出现影子',      'spawn',      'EN1',   0),
    (207, '芬 进入攻击前摇',          'dmg_ally',   'ALLY',  0),   # 芬首次受伤 = 敌人起手
    (221, '芬 命中 猎狗pro 1',        'dmg_enemy',  'EN1',   0),
    (236, '芬 阻挡 猎狗pro 1',        'watch',      '-',     0),
    (253, '芬命中 猎狗pro 1',         'dmg_enemy',  'EN1',   1),
    (255, '猎狗pro 1 命中 芬',        'dmg_ally',   'ALLY',  1),
    (285, '芬 命中 猎狗pro 1',        'dmg_enemy',  'EN1',   2),
    (298, '猎狗pro 1 命中 芬',        'dmg_ally',   'ALLY',  2),
    (317, '芬 命中 猎狗pro 1',        'dmg_enemy',  'EN1',   3),
    (340, '猎狗pro 1 命中 芬',        'dmg_ally',   'ALLY',  3),
    (349, '芬 命中 猎狗pro 1',        'dmg_enemy',  'EN1',   4),
    (367, '猎狗pro 2 出现影子',       'spawn',      'EN2',   0),
    (381, '芬 击杀 猎狗pro 1',        'kill',       'EN1',   0),
    (432, '芬 命中 猎狗pro 2',        'dmg_enemy',  'EN2',   0),
    (438, '月见夜 远程命中 猎狗pro 2', 'dmg_enemy',  'EN2',   1),
    (443, '芬 阻挡 猎狗pro 2',        'watch',      '-',     1),
    (461, '猎狗pro 2 命中 芬',        'dmg_ally',   'ALLY',  6),   # 标定只标了部分，序号取实测位置
    (464, '芬 击杀 猎狗pro 2',        'kill',       'EN2',   0),
]


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
    # 敌方出现顺序（只计敌方）
    order, n = {}, 0
    for e in sorted((x for x in ev if x['type'] == 'spawn'), key=lambda z: z['frame']):
        if any(a in str(e.get('name') or '') for a in ALLY_NAMES):
            continue
        n += 1
        order[e.get('uid')] = n

    # 构造索引表
    idx = {}
    for e in ev:
        t, uid = e['type'], e.get('uid')
        nm = str(e.get('name') or '')
        if t == 'spawn' and uid in order:
            idx.setdefault(('spawn', f'EN{order[uid]}'), []).append(e['frame'])
        elif t in ('damage', 'damage_first'):
            if any(a in nm for a in ALLY_NAMES):
                idx.setdefault(('dmg_ally', 'ALLY'), []).append(e['frame'])
            elif uid in order:
                idx.setdefault(('dmg_enemy', f'EN{order[uid]}'), []).append(e['frame'])
        elif t in ('despawn', 'kill') and uid in order:
            idx.setdefault(('kill', f'EN{order[uid]}'), []).append(e['frame'])
    for k in idx:
        idx[k] = sorted(set(idx[k]))

    print('模拟器事件索引表:')
    for k in sorted(idx, key=str):
        print(f'  {k}: {len(idx[k])} 个 -> {idx[k][:8]}{"..." if len(idx[k]) > 8 else ""}')

    print(f'\n{"标定帧":>6} {"说明":>22} {"类别":>10} {"目标":>6} {"#":>3} '
          f'{"模拟器帧":>9} {"偏差":>6}')
    print('-' * 78)
    diffs = []
    for f, desc, cat, tgt, i in MAP:
        frames = idx.get((cat, tgt), [])
        if i < len(frames):
            ef = frames[i]
            d = abs(ef - f)
            diffs.append(d)
            print(f'{f:>6} {desc:>22} {cat:>10} {tgt:>6} {i:>3} {ef:>9} {ef - f:>+6}'
                  + ('  OK' if d <= 6 else '  ★偏大'))
        else:
            print(f'{f:>6} {desc:>22} {cat:>10} {tgt:>6} {i:>3} {"(缺)":>9} {"-":>6}')
    print('-' * 78)
    if diffs:
        hit = sum(1 for d in diffs if d <= 6)
        print(f'可对齐 {len(diffs)}/{len(MAP)}；**|偏差|≤6 帧 {hit} 条**；'
              f'**平均 {sum(diffs)/len(diffs):.2f} 帧**；最大 {max(diffs)} 帧')
        print('偏差分布: ' + ', '.join(str(d) for d in sorted(diffs)))


if __name__ == '__main__':
    main()
