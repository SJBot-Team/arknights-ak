# -*- coding: utf-8 -*-
r"""t200_green_tiles.py — 从战斗截图里找出"可部署地块"（绿色高亮）的矩形中心。

用法（在**已点选干员卡片**的暂停画面上）：
    python t200_green_tiles.py <shot.png>

输出：每个绿色连通块的 bbox 与中心（1920×1080 原图坐标），按 x 排序。
"""
from __future__ import annotations

import sys

import numpy as np
from PIL import Image

sys.stdout.reconfigure(encoding='utf-8')


def main() -> int:
    path = sys.argv[1]
    im = Image.open(path).convert('RGB')
    W, H = im.size
    a = np.asarray(im).astype(np.int16)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    # 绿色可部署高亮：G 明显高于 R/B，且整体亮度不是过暗
    mask = (g > r + 25) & (g > b + 25) & (g > 90)
    print(f'图 {W}x{H}｜绿色像素 {int(mask.sum())}')

    # 简易连通块（按行扫描 + BFS，规模小够用）
    lab = np.zeros((H, W), dtype=np.int32)
    cur = 0
    boxes = []
    ys, xs = np.nonzero(mask)
    pts = set(zip(ys.tolist(), xs.tolist()))
    seen = set()
    for y0, x0 in zip(ys.tolist(), xs.tolist()):
        if (y0, x0) in seen:
            continue
        cur += 1
        stack = [(y0, x0)]
        seen.add((y0, x0))
        miny = maxy = y0
        minx = maxx = x0
        n = 0
        while stack:
            y, x = stack.pop()
            n += 1
            miny, maxy = min(miny, y), max(maxy, y)
            minx, maxx = min(minx, x), max(maxx, x)
            for dy in (-2, -1, 0, 1, 2):
                for dx in (-2, -1, 0, 1, 2):
                    p = (y + dy, x + dx)
                    if p in pts and p not in seen:
                        seen.add(p)
                        stack.append(p)
        if n >= 400:      # 过滤噪点
            boxes.append((minx, miny, maxx, maxy, n))

    boxes.sort(key=lambda t: t[0])
    print(f'有效绿色块 {len(boxes)} 个：')
    for i, (minx, miny, maxx, maxy, n) in enumerate(boxes):
        cx, cy = (minx + maxx) // 2, (miny + maxy) // 2
        print(f'  #{i}  bbox=({minx},{miny})-({maxx},{maxy})  中心=({cx},{cy})  '
              f'宽{maxx-minx} 高{maxy-miny}  像素{n}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
