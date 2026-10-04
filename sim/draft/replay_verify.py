# -*- coding: utf-8 -*-
"""verify_events.py — ★以"事件精确帧"为口径，逐条判定模拟器准确性

## 依目标③
「以**事件发生的精确帧**作为模拟准确性的判定口径」。
本脚本把**用户标定表**的每一条事件与**模拟器**的门控事件逐条对齐，输出偏差统计。

## 标定表（用户提供，1-1 标定对局前 21 条）
列：`秒 | 该秒初始费用 | 帧 | 费用变化 | 操作 | 格子 | 单位 | 方向 | 动画层`
- **帧号 = 秒×30 + 帧**
- 关键操作：**部署芬 @D6 朝左（帧10，8费）**、**部署月见夜 @D4 朝上（帧411，14费）**

## 对齐口径
| 标定"动画层" | 模拟器事件类型 | 说明 |
|---|---|---|
| 出现影子 | `spawn` | 敌人出生（影子先于本体） |
| 进入攻击前摇 | `damage_first`（近似） | 攻击前摇开始（模拟器用首次伤害近似） |
| 命中 | `damage` | 造成伤害的时刻 |
| 阻挡 | （模拟器以"进入阻挡范围"计，暂用 `damage` 邻近） | — |
| 击杀 | `despawn` / 敌人 hp≤0 | — |

用法：
    python replay_verify.py
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
DIR_MAP = {'左': '左', '右': '右', '上': '上', '下': '下'}

# (帧, 干员, 显示格, 方向, 费用覆盖)
DEPLOYS = [(10, FANG, 'D6', '左', 8), (411, MIDN, 'D4', '上', None)]

# 用户标定表的事件（帧, 单位, 动画层描述）
CALIB = [
    (94, '猎狗pro 1', '出现影子'),
    (207, '芬', '进入攻击前摇'),
    (221, '猎狗pro 1', '芬 命中'),
    (236, '猎狗pro 1', '芬 阻挡'),
    (253, '猎狗pro 1', '芬命中'),
    (255, '芬', '猎狗pro 1 命中'),
    (285, '猎狗pro 1', '芬 命中'),
    (298, '芬', '猎狗pro 1 命中'),
    (317, '猎狗pro 1', '芬 命中'),
    (340, '芬', '猎狗pro 1 命中'),
    (349, '猎狗pro 1', '芬 命中'),
    (367, '猎狗pro 2', '出现影子'),
    (381, '猎狗pro 1', '芬 击杀'),
    (432, '猎狗pro 2', '芬 命中'),
    (438, '猎狗pro 2', '月见夜 远程命中'),
    (443, '猎狗pro 2', '芬 阻挡'),
    (461, '芬', '猎狗pro 2 命中'),
    (464, '猎狗pro 2', '芬 击杀'),
]

# 标定 → 模拟器事件类型的映射
KIND_MAP = {
    '出现影子': ('spawn',),
    '进入攻击前摇': ('damage_first', 'damage'),
    # ★"命中"必须同时含 `damage_first`：模拟器把"某单位的第一次受伤"记为 `damage_first`、
    #   后续记为 `damage`；若只匹配 `damage`，"首次命中"会被错配到第二次伤害（曾造成 +47 帧假偏差）。
    '命中': ('damage', 'damage_first'),
    '阻挡': ('damage', 'damage_first', 'spawn'),
    '击杀': ('despawn', 'damage', 'damage_first'),
}


def to_rc(tile: str):
    """显示格 → (row, col)：row = 字母序号−1、col = 数字−1。"""
    return ord(tile[0].upper()) - 65, int(tile[1:]) - 1


def classify(desc: str):
    for k, v in KIND_MAP.items():
        if k in desc:
            return k, v
    return '?', ()


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
    kinds = {}
    for e in ev:
        kinds.setdefault(e['type'], []).append(e)
    print(f'模拟器事件类型统计: ' + ', '.join(f'{k}={len(v)}' for k, v in sorted(kinds.items())))
    print(f'\n{"标定帧":>6} {"单位(受害者)":>12} {"动画层":>16} {"匹配类型":>12} {"模拟器帧":>9} {"偏差":>6}')
    print('-' * 78)
    diffs = []
    hit = 0
    for f, unit, desc in CALIB:
        cat, types = classify(desc)
        cands = []
        for t in types:
            for e in kinds.get(t, []):
                # ★按"受害者名"限定（标定的"单位"列 = 受害者；模拟器 damage 事件的 name 亦是受害者）
                en = str(e.get('name') or '')
                if unit and en and unit not in en and en not in unit:
                    continue
                cands.append((abs(e['frame'] - f), e['frame'], t))
        if not cands:
            # 退化为"不限名"的宽松匹配（避免漏配），并标注
            for t in types:
                for e in kinds.get(t, []):
                    cands.append((abs(e['frame'] - f), e['frame'], t + '~'))
        if not cands:
            print(f'{f:>6} {unit:>12} {desc:>16} {"(无同类事件)":>12} {"-":>9} {"-":>6}')
            continue
        d, ef, t = min(cands)
        diffs.append(d)
        if d <= 6:
            hit += 1
        print(f'{f:>6} {unit:>12} {desc:>16} {t:>12} {ef:>9} {ef - f:>+6}'
              + ('  OK' if d <= 6 else '  ★偏大'))
    print('-' * 72)
    if diffs:
        print(f'可对齐事件 {len(diffs)}/{len(CALIB)}；'
              f'其中 |偏差| ≤ 6 帧的 {hit} 条；'
              f'平均 |偏差| = {sum(diffs) / len(diffs):.2f} 帧；'
              f'最大 = {max(diffs)} 帧')
        print(f'偏差分布: ' + ', '.join(f'{d}' for d in sorted(diffs)))
    else:
        print('无可对齐事件')


if __name__ == '__main__':
    main()
