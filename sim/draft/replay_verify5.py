# -*- coding: utf-8 -*-
"""replay_verify5.py — ★用「受害者 + 攻击者」精确定位的事件对照（标定命名已修正）

## 命名修正（依用户 2026-09-15 确认）
实际出怪顺序：**第 1 只 = `enemy_1000_gopro_2`「猎狗pro」(hp1700)**、
**第 2 只 = `enemy_1000_gopro`「猎狗」(hp820)**
⇒ 标定表已按此修正（`猎狗pro 1→猎狗pro`、`猎狗pro 2→猎狗`）。

## 定位键
`(类别, 受害者, 攻击者, 序号)`，其中类别 ∈ `spawn / dmg / kill`：
- `dmg` 事件由 `extract_events` 提供 `name`（受害者）与 `src`（攻击者）；
- **攻击者信息是关键**：同一只敌人可能被芬与月见夜分别打（1-1 中 EN2 只被月见夜打）。
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
DIR_MAP = {'左': '左', '上': '上'}
DEPLOYS = [(10, FANG, 'D6', '左', 8), (411, MIDN, 'D4', '上', None)]

# ★人工对应表（命名已按实际出怪修正）：
#   (标定帧, 说明, 类别, 受害者, 攻击者, 序号)
#   受害者/攻击者用**标定表里的名字**（"猎狗pro"=第1只、"猎狗"=第2只）；"-" 表示不限定。
MAP = [
    (94,  '猎狗pro 出现影子',            'spawn', '猎狗pro', '-',      0),
    (207, '芬 进入攻击前摇',              'dmg',   '芬',      '猎狗pro', 0),
    (221, '芬 命中 猎狗pro',              'dmg',   '猎狗pro', '芬',     0),
    (236, '芬 阻挡 猎狗pro',              'watch', '-',       '-',      0),
    (253, '芬命中 猎狗pro',               'dmg',   '猎狗pro', '芬',     1),
    (255, '猎狗pro 命中 芬',              'dmg',   '芬',      '猎狗pro', 1),
    (285, '芬 命中 猎狗pro',              'dmg',   '猎狗pro', '芬',     2),
    (298, '猎狗pro 命中 芬',              'dmg',   '芬',      '猎狗pro', 2),
    (317, '芬 命中 猎狗pro',              'dmg',   '猎狗pro', '芬',     3),
    (340, '猎狗pro 命中 芬',              'dmg',   '芬',      '猎狗pro', 3),
    (349, '芬 命中 猎狗pro',              'dmg',   '猎狗pro', '芬',     4),
    (367, '猎狗 出现影子',                'spawn', '猎狗',    '-',      0),
    (381, '芬 击杀 猎狗pro',              'kill',  '猎狗pro', '-',      0),
    (432, '芬 命中 猎狗',                 'dmg',   '猎狗',    '芬',     0),
    (438, '月见夜 远程命中 猎狗',          'dmg',   '猎狗',    '月见夜',  0),
    (443, '芬 阻挡 猎狗',                 'watch', '-',       '-',      1),
    (461, '猎狗 命中 芬',                 'dmg',   '芬',      '猎狗',   1),
    (464, '芬 击杀 猎狗',                 'kill',  '猎狗',    '-',      0),
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
        if str(e.get('name') or '') in ('芬', '月见夜', '令', '蕾缪安'):
            continue
        n += 1
        order[e.get('uid')] = n
    # 序号 → 名称（用于把标定名映射到模拟器实例名）
    idx_name = {}
    for e in ev:
        if e['type'] == 'spawn' and e.get('uid') in order:
            idx_name[order[e['uid']]] = str(e.get('name'))

    # 索引表： (类别, 受害者名, 攻击者名) -> [帧...]
    idx = {}
    for e in ev:
        t, uid = e['type'], e.get('uid')
        nm = str(e.get('name') or '')
        if t == 'spawn' and uid in order:
            idx.setdefault(('spawn', nm, '-'), []).append(e['frame'])
        elif t in ('damage', 'damage_first'):
            idx.setdefault(('dmg', nm, str(e.get('src') or '-')), []).append(e['frame'])
        elif t in ('despawn', 'kill') and uid in order:
            idx.setdefault(('kill', nm, '-'), []).append(e['frame'])
    for k in idx:
        idx[k] = sorted(set(idx[k]))

    print('模拟器事件索引（(类别,受害者,攻击者): 帧列表）:')
    for k in sorted(idx, key=str):
        print(f'  {k}: {idx[k]}')
    print('\n敌方出现顺序:', {v: k for k, v in idx_name.items()} if False else
          {k: v for k, v in sorted(idx_name.items())})

    print(f'\n{"标定帧":>6} {"说明":>20} {"类别":>6} {"受害者":>8} {"攻击者":>8} {"#":>3} '
          f'{"模拟器帧":>9} {"偏差":>6}')
    print('-' * 82)
    diffs = []
    for f, desc, cat, vic, atk, i in MAP:
        if cat == 'watch':
            print(f'{f:>6} {desc:>20} {"(观察)":>6} {vic:>8} {atk:>8} {i:>3} {"-":>9} {"-":>6}')
            continue
        key = (cat, vic, atk) if cat == 'dmg' else (cat, vic, '-')
        frames = idx.get(key, [])
        if i < len(frames):
            ef = frames[i]
            d = abs(ef - f)
            diffs.append(d)
            print(f'{f:>6} {desc:>20} {cat:>6} {vic:>8} {atk:>8} {i:>3} {ef:>9} {ef - f:>+6}'
                  + ('  OK' if d <= 6 else '  ★偏大'))
        else:
            print(f'{f:>6} {desc:>20} {cat:>6} {vic:>8} {atk:>8} {i:>3} {"(缺)":>9} {"-":>6}')
    print('-' * 82)
    if diffs:
        hit = sum(1 for d in diffs if d <= 6)
        print(f'可对齐 {len(diffs)}/{len([m for m in MAP if m[2] != "watch"])}；'
              f'**|偏差|≤6 帧 {hit} 条**；**平均 {sum(diffs)/len(diffs):.2f} 帧**；最大 {max(diffs)} 帧')
        print('偏差分布: ' + ', '.join(str(d) for d in sorted(diffs)))


if __name__ == '__main__':
    main()
