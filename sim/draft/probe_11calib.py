# -*- coding: utf-8 -*-
"""probe_11calib.py — 1-1 标定对局复刻前的准备：干员 id、地图坐标约定、费用账本自检"""
from __future__ import annotations

import json
import sys

sys.path.insert(0, r'C:\Users\23922\Documents\ds_harness\ak\sim\draft')
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim import data as D          # noqa: E402

# ---- 标定表（用户提供，帧 = 该秒内帧位置）----
CALIB = [
    # (秒, 该秒初始费用, 帧, 费用变化, 操作, 格子, 单位, 方向, 动画层)
    (0, 10, 10, -8, '部署', 'D6', '芬', '左', ''),
    (3, 5, 4, None, '', 'D1', '猎狗pro 1', '', '出现影子'),
    (6, 8, 27, None, '', '', '芬', '', '进入攻击前摇'),
    (7, 9, 11, None, '', '', '猎狗pro 1', '', '芬 命中'),
    (7, 9, 26, None, '', '', '猎狗pro 1', '', '芬 阻挡'),
    (8, 10, 13, None, '', '', '猎狗pro 1', '', '芬命中'),
    (8, 10, 15, None, '', '', '芬', '', '猎狗pro 1 命中'),
    (9, 11, 15, None, '', '', '猎狗pro 1', '', '芬 命中'),
    (9, 11, 28, None, '', '', '芬', '', '猎狗pro 1 命中'),
    (10, 12, 17, None, '', '', '猎狗pro 1', '', '芬 命中'),
    (11, 13, 10, None, '', '', '芬', '', '猎狗pro 1 命中'),
    (11, 13, 19, None, '', '', '猎狗pro 1', '', '芬 命中'),
    (12, 14, 7, None, '', 'G5', '猎狗pro 2', '', '出现影子'),
    (12, 14, 21, None, '', '', '猎狗pro 1', '', '芬 击杀'),
    (13, 15, 21, -14, '部署', 'D4', '月见夜', '上', ''),
    (14, 3, 12, None, '', '', '猎狗pro 2', '', '芬 命中'),
    (14, 3, 18, None, '', '', '猎狗pro 2', '', '月见夜 远程命中'),
    (14, 3, 23, None, '', '', '猎狗pro 2', '', '芬 阻挡'),
    (15, 4, 11, None, '', '', '芬', '', '猎狗pro 2 命中'),
    (15, 4, 14, None, '', '', '猎狗pro 2', '', '芬 击杀'),
    (18, 7, 11, 6, '', '', '芬', '', '技能自动开启'),
]


def frame_of(sec, fr):
    return sec * 30 + fr


def main():
    print('=== 一、标定表的帧号换算 ===')
    for sec, c0, fr, dc, op, tile, unit, direc, anim in CALIB:
        f = frame_of(sec, fr)
        tag = ''
        if dc is not None:
            tag = f'  费用变化 {dc:+d}'
        if op:
            tag += f'  ★{op} {unit} @{tile} 朝{direc}'
        if anim:
            tag += f'  [{anim}]'
        print(f'  {sec:>2}s+{fr:>2}帧 = 帧 {f:>4} ({f/30:>6.2f}s)  该秒初始费用={c0}{tag}')

    print('\n=== 二、费用账本自检（用标定表的"该秒初始费用"列）===')
    init_cost = 10.0
    cap = 99.0
    cur = init_cost
    last_f = 0.0
    ok_all = True
    for sec, c0, fr, dc, op, tile, unit, direc, anim in CALIB:
        f = frame_of(sec, fr)
        t = f / 30.0
        cur = min(cap, cur + (t - last_f))
        if dc:
            cur += dc
        # 与该行"该秒初始费用"比较（该列是这一秒开始时的费用）
        sec_start_cost = None
        # 用"该秒起点的费用"重算：从 init 涨到 sec 秒，再扣掉此前所有部署
        spent = sum(-d for (_s, _c, _fr, d, *_) in CALIB[:CALIB.index((sec, c0, fr, dc, op, tile, unit, direc, anim)) + 1] if d and d < 0)
        gained = sum(d for (_s, _c, _fr, d, *_) in CALIB[:CALIB.index((sec, c0, fr, dc, op, tile, unit, direc, anim)) + 1] if d and d > 0)
        sec_start_cost = init_cost + sec - spent + gained
        mark = 'OK' if abs(sec_start_cost - c0) < 0.01 else '★差异'
        if mark != 'OK':
            ok_all = False
        print(f'  {sec:>2}s: 标定值={c0:>4}  账本推算={sec_start_cost:>6.1f}  {mark}')
        last_f = t
    print(f'  ⇒ 费用账本与标定表{"完全一致 ✓" if ok_all else "存在差异（见上）"}')

    print('\n=== 三、干员 id ===')
    ct = D.load_table('character_table.json')
    for cid, c in ct.items():
        nm = c.get('name')
        if nm in ('芬', '月见夜'):
            prof = c.get('profession')
            pos = c.get('position')
            print(f'  {nm}: {cid}  职业={prof}  位置={pos}')

    print('\n=== 四、1-1 地图坐标与可部署性 ===')
    lv = D.load_level('obt/main/level_main_01-01')
    md = lv['mapData']
    tiles, codes = md['tiles'], md['map']
    R, C = len(codes), len(codes[0])
    print(f'  地图 {R} 行 x {C} 列（显示行号 1..{R}，列号 A..{chr(64 + C)}）')
    for r in range(R):
        row = []
        for c in range(C):
            t = tiles[codes[r][c]]
            b = t.get('buildableType', '')
            h = t.get('heightType', '')
            ch = {'NONE': '#', 'MELEE': '.', 'RANGED': '^'}.get(b, '?')
            if b == 'ALL' or b == 'MELEE,RANGED':
                ch = '*'
            row.append(ch)
        print(f'  第{r + 1}行(row={r}): ' + ' '.join(row))
    print('  （# 不可部署  . 近战  ^ 远程/高台）')
    print('\n  标定用到的格子：D6（芬）、D4（月见夜）、D1/G5（敌人生成点）')
    for name, (col, rownum) in (('D6', ('D', 6)), ('D4', ('D', 4)), ('D1', ('D', 1)), ('G5', ('G', 5))):
        c = ord(col) - 65
        r = rownum - 1
        if 0 <= r < R and 0 <= c < C:
            t = tiles[codes[r][c]]
            print(f'  {name} → row={r} col={c}  buildable={t.get("buildableType")}  height={t.get("heightType")}')


if __name__ == '__main__':
    main()
