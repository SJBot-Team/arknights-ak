# -*- coding: utf-8 -*-
"""render_map.py — 把关卡地形画成 PNG（用于和实机截图比对朝向/高台分布）。

输出：.tmp/map_render.png
  * 绿边格 = 可部署；灰色 = 不可部署
  * 高台 = 浅蓝底，地面 = 米色底，坑 = 深灰
  * 红框 = 敌人出生点，蓝框 = 目标点（终点）
  * 左上角标注 (row, col)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

try:
    import cv2
    import numpy as np
except Exception as e:                                     # pragma: no cover
    print('need cv2/numpy:', e)
    raise

from ak_sim import scenario_h124 as S                      # noqa: E402
from ak_sim.engine import Battle                           # noqa: E402

CELL = 60
PAD = 40


def main():
    b = Battle(S.LEVEL, seed=0, record=False)
    m = b.map
    H, W = m.height, m.width
    img = np.full((H * CELL + PAD * 2, W * CELL + PAD * 2, 3), 255, np.uint8)

    print(f'地图 {H}×{W}')
    # 出生点 / 终点（关卡 route 数据）
    starts, ends = set(), set()
    for key, rt in (getattr(m, 'routes', None) or {}).items():
        pass
    for route in (b.level.get('routes') or []):
        sp = route.get('startPosition') or {}
        ep = route.get('endPosition') or {}
        if 'row' in sp and 'col' in sp:
            starts.add((int(sp['row']), int(sp['col'])))
        if 'row' in ep and 'col' in ep:
            ends.add((int(ep['row']), int(ep['col'])))
    print('出生点:', sorted(starts))
    print('终点  :', sorted(ends))

    for r in range(H):
        for c in range(W):
            t = m.tile(r, c)
            ht = str(getattr(t, 'height_type', 'LOWLAND')).upper()
            if t is None or getattr(t, 'is_hole', False):
                col = (60, 60, 60)
            elif ht == 'HIGHLAND':
                col = (235, 205, 150)
            else:
                col = (215, 230, 245)
            y0, x0 = PAD + r * CELL, PAD + c * CELL
            cv2.rectangle(img, (x0, y0), (x0 + CELL, y0 + CELL), col, -1)
            # 可部署性：近战位（地面/高台分别判）
            melee_ok = m.can_deploy(r, c, melee=True)
            ranged_ok = m.can_deploy(r, c, melee=False)
            if melee_ok:
                cv2.circle(img, (x0 + 18, y0 + CELL - 18), 7, (0, 160, 0), -1)
            if ranged_ok:
                cv2.circle(img, (x0 + 42, y0 + CELL - 18), 7, (200, 90, 0), -1)
            cv2.putText(img, f'{r},{c}', (x0 + 4, y0 + 16), cv2.FONT_HERSHEY_SIMPLEX,
                        0.36, (90, 90, 90), 1, cv2.LINE_AA)
            cv2.rectangle(img, (x0, y0), (x0 + CELL, y0 + CELL), (150, 150, 150), 1)
    for (r, c) in starts:
        if 0 <= r < H and 0 <= c < W:
            y0, x0 = PAD + r * CELL, PAD + c * CELL
            cv2.rectangle(img, (x0 + 2, y0 + 2), (x0 + CELL - 2, y0 + CELL - 2), (0, 0, 230), 3)
    for (r, c) in ends:
        if 0 <= r < H and 0 <= c < W:
            y0, x0 = PAD + r * CELL, PAD + c * CELL
            cv2.rectangle(img, (x0 + 6, y0 + 6), (x0 + CELL - 6, y0 + CELL - 6), (230, 0, 0), 3)

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '.tmp', 'map_render.png')
    out = os.path.abspath(out)
    cv2.imwrite(out, img)
    print('写出', out)
    # ASCII 版本便于文字比对
    print('\nASCII（H=高台, .=地面, #=坑/不可通行；行号自上而下 = row 0..N）')
    for r in range(H):
        row = ''
        for c in range(W):
            t = m.tile(r, c)
            if t is None or getattr(t, 'is_hole', False):
                row += '#'
            elif str(getattr(t, 'height_type', 'LOWLAND')).upper() == 'HIGHLAND':
                row += 'H'
            else:
                row += '.'
        print(f'{r:>2} {row}')


if __name__ == '__main__':
    main()
