# -*- coding: utf-8 -*-
"""sweep_enemy_speed.py — ★分辨"敌人有效移速"：moveSpeed × moveMultiplier 到底是多少？

## 为什么必须查
补了移动惯性后仍有 ~25 帧差，且**不能用阻挡规则解释**：
标定要求"敌人 0.1 圆**在帧 432 之前**就进入芬的 2 格"（芬前摇 18 ⇒ 索敌 ≈ 414），
而模拟器里该敌人**靠自己走**要到 **439** 才满足（帧 414 时它还在 y≈4.9，离芬的范围格还有 0.8 格）。
⇒ 在 `moveSpeed=1.9`、出生点 = 格 (6,4) 中心 (4.5,6.5)、`moveMultiplier=0.5`（关卡实测值）下，
   **几何上不可能在 414 进入范围**（需要 ~0.79 格的额外行程）。

⇒ 本脚本扫描"敌人有效移速倍率"，同时报 **(a) 阻挡帧误差**（标定 236/443）、**(b) 伤害帧误差**。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from sweep_hit_volume import run, score     # noqa: E402
from sweep_block_frames import CALIB_BLOCK  # noqa: E402


def blocks(b):
    return [l.frame for l in b.logs if l.kind == 'block']


def berr(b):
    bl = blocks(b)
    if len(bl) < len(CALIB_BLOCK):
        return 999.0
    return sum(abs(bl[i] - CALIB_BLOCK[i]) for i in range(len(CALIB_BLOCK))) / len(CALIB_BLOCK)


print(f'{"阻挡margin":>10} {"移速倍率":>8} {"等效移速":>8} {"阻挡帧":>13} {"阻挡误差":>8} '
      f'{"平均":>6} {"≤6帧":>5} {"最大":>5}')
for margin in (0.1, 1.0):
    for mul in (0.5, 0.6, 0.65, 0.7, 0.75, 0.85, 1.0):
        opts = {'block_cell_margin': margin, 'move_multiplier_override': mul}
        b = run(opts)
        a, h, m, _d = score(b)
        print(f'{margin:>10.2f} {mul:>8.2f} {1.9 * mul:>8.3f} {str(blocks(b)):>13} '
              f'{berr(b):>8.1f} {a:>6.2f} {h:>5} {m:>5}')
print(f'\n标定阻挡帧 = {CALIB_BLOCK}')
