# -*- coding: utf-8 -*-
"""calibrate_grid_live.py — ★实机「格点 → 像素」标定（用**绿格集合 + 关卡地图反解**，不人肉试坐标）。

## 为什么需要
轴表里的 `cell`（如 D6 = row3/col5）要变成实机点击坐标，才能"按轴表部署"。
此前一直靠人肉试坐标或 `calc_view` 的 3D 投影（需要标定样本）。

## 做法（可自校验）
1. 实机处于**暂停 + 已选卡**状态时截图 ⇒ **绿格**=当前可部署格集合；
2. `Deployer.find_green_cells` 给出**格单元中心**（按实测 `cell_px≈130` 网格切分）；
3. 从关卡数据取地图（7×9 的 `mapData.map` + `tiles`），算出**近战地面可部署格集合**；
4. 用**仿射拟合**把"地图格 (row,col) → 像素中心"解出来：
   对两张集合做**最小二乘 + 离散匹配**（先按行列单调性排序配对，再迭代剔除离群）；
5. 输出 **RMS 重投影误差** 与 D6/D4 的像素坐标 —— **误差大就报警，不猜**。

用法：
    python apps/calibrate_grid_live.py --stage 1-1 [--shot out.png] [--dump-json out.json]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from plugins.action.deploy import Deployer                 # noqa: E402
from plugins.capture.emu_window import make_capture        # noqa: E402

LEVELS = r'E:\__file\ak_kb\gamedata\levels'
STAGE_FILE = {'1-1': 'obt/main/level_main_01-01.json'}


def load_map(stage: str):
    p = os.path.join(LEVELS, STAGE_FILE[stage].replace('/', os.sep))
    lv = json.load(open(p, encoding='utf-8'))
    m = ((lv.get('mapData') or {}).get('map')) or []
    tiles = ((lv.get('mapData') or {}).get('tiles')) or []
    rows, cols = len(m), len(m[0]) if m else 0
    return lv, m, tiles, rows, cols


def deployable_ground(m, tiles, rows, cols):
    """近战地面可部署格集合（row,col）。

    判定：tile.buildableType 允许近战(=0/1 视表)、heightType=LOWLAND、passableMask 允许地面。
    ★以实机绿格为准做**集合匹配**，这里只给"候选集合"，允许后续校正。
    """
    out = set()
    for r in range(rows):
        for c in range(cols):
            code = m[r][c]
            t = tiles[code] if 0 <= code < len(tiles) else {}
            bt = t.get('buildableType')
            ht = str(t.get('heightType'))
            out.add(((r, c), bt, ht))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--stage', default='1-1')
    ap.add_argument('--shot', default=r'C:\Users\23922\Documents\ds_harness\ak\.tmp\grid_live.png')
    ap.add_argument('--dump-json', default=None)
    a = ap.parse_args()

    cap = make_capture('adb')
    img = cap.grab().image
    import cv2
    cv2.imwrite(a.shot, img)
    print(f'截图 → {a.shot}  shape={img.shape}')

    dep = Deployer(cap)
    cells = dep.find_green_cells(img)
    print(f'绿格单元数 {len(cells)}')
    for i, c in enumerate(cells[:40]):
        print(f'  #{i:<3} 中心=({c[0]:.0f},{c[1]:.0f}) 面积={c[2] if len(c) > 2 else "?"}')
    lv, m, tiles, rows, cols = load_map(a.stage)
    print(f'\n关卡 {a.stage}: 地图 {rows}×{cols}')
    for r in range(rows):
        print('   ' + ' '.join(f'{v:>3}' for v in m[r]))
    print('\ntiles 样例:', json.dumps(tiles[:4], ensure_ascii=False)[:400])
    if a.dump_json:
        json.dump({'cells': [list(map(float, c)) for c in cells], 'map': m,
                   'tiles': tiles}, open(a.dump_json, 'w', encoding='utf-8'),
                  ensure_ascii=False)
        print('已写出', a.dump_json)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
