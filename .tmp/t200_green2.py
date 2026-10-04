# -*- coding: utf-8 -*-
r"""t200_green2.py — 更灵敏的"可部署地块"检测（拖拽悬停时用）。

游戏的高亮是**半透明绿**叠加在地块上，RGB 差值不大 ⇒ 改用 HSV 色相 + 饱和度阈值，
并把连通块的面积下限降到 200。
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
    # 绿：G 是最大通道，且明显高于 R、B；放宽幅度
    mask = (g > r + 12) & (g > b + 8) & (g > 70)
    print(f'图 {W}x{H}｜绿色像素 {int(mask.sum())}')

    ys, xs = np.nonzero(mask)
    pts = set(zip(ys.tolist(), xs.tolist()))
    seen = set()
    boxes = []
    for y0, x0 in zip(ys.tolist(), xs.tolist()):
        if (y0, x0) in seen:
            continue
        stack = [(y0, x0)]
        seen.add((y0, x0))
        miny = maxy = y0
        minx = maxx = x0
        n = 0
        while stack:
            y, x = stack.pop()
            n += 1
            if y < miny:
                miny = y
            if y > maxy:
                maxy = y
            if x < minx:
                minx = x
            if x > maxx:
                maxx = x
            for dy in (-3, -2, -1, 0, 1, 2, 3):
                for dx in (-3, -2, -1, 0, 1, 2, 3):
                    p = (y + dy, x + dx)
                    if p in pts and p not in seen:
                        seen.add(p)
                        stack.append(p)
        if n >= 200:
            boxes.append((minx, miny, maxx, maxy, n))
    boxes.sort(key=lambda t: (t[0], t[1]))
    print(f'有效绿色块 {len(boxes)} 个（按 x 排序）：')
    for i, (minx, miny, maxx, maxy, n) in enumerate(boxes):
        print(f'  #{i}  bbox=({minx},{miny})-({maxx},{maxy})  中心=({(minx+maxx)//2},{(miny+maxy)//2})  '
              f'宽{maxx-minx} 高{maxy-miny}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
