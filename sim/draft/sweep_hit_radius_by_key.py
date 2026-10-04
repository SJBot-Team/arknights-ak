# -*- coding: utf-8 -*-
"""sweep_hit_radius_by_key.py — ★按**敌人 key** 分别设定受击半径，检验能否同时满足"阻挡帧 + 伤害帧"。

## 动机（L1-03 / L2-03 的耦合）
实测：`margin 1.0`（进 3×3 邻域）伤害最优但阻挡帧偏 −32/−31；
`margin 0.1`（≈进入阻挡者所在格）阻挡帧只差 −4/−1，**但敌人 #2（猎狗）的伤害退化 +25 帧**。
⇒ 假设：**两种敌人的受击体积不同**（此前一律 0.1）。
客户端 prefab 的逐敌半径虽已定位（`battle/enm_pfb_N.ab`，`CircleCollider2D.m_Radius`），
但本机缺 `UnityPy` 无法即时解析 ⇒ **先在模拟端反推**：扫描"猎狗"的受击半径，
看是否存在一组取值使 **阻挡帧≈[236,443] 且全部伤害 ≤6 帧**。

## 输出
对每个 (margin, 猎狗半径) 组合：阻挡帧、平均偏差、≤6帧数、最大偏差。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

import ak_sim.engine as E                      # noqa: E402
from ak_sim.engine import Battle               # noqa: E402
from ak_sim.scenario import Scenario           # noqa: E402

# 打补丁：支持按 key 覆盖受击半径
_orig_spawn = Battle._spawn_enemy


def _spawn_patched(self, a):
    _orig_spawn(self, a)
    ov = getattr(self, 'hit_radius_by_key', None)
    if ov and self.units:
        u = max(self.units.values(), key=lambda z: z.uid)
        if u.key in ov:
            u.hit_radius = float(ov[u.key])


Battle._spawn_enemy = _spawn_patched

from sweep_hit_volume import run, score          # noqa: E402


def run2(opts):
    b = run(opts)
    return b


if __name__ == '__main__':
    CAL = [236, 443]
    print(f'{"margin":>7} {"猎狗半径":>8} {"阻挡帧":>12} {"阻挡偏差":>10} '
          f'{"伤害平均":>8} {"≤6帧":>5} {"最大":>5}')
    for margin in (0.1, 0.3, 0.5):
        for r in (0.1, 0.3, 0.5, 0.8, 1.0):
            opts = {'block_cell_margin': margin, 'block_snap': False,
                    'hit_radius_by_key': {'enemy_1000_gopro': r}}
            b = run2(opts)
            bl = [l.frame for l in b.logs if l.kind == 'block']
            a, h, m, _ = score(b)
            dv = (bl[0] - CAL[0], bl[1] - CAL[1]) if len(bl) >= 2 else None
            print(f'{margin:>7} {r:>8} {str(bl):>12} {str(dv):>10} '
                  f'{a:>8.2f} {h:>5} {m:>5}')
    print('\n目标：阻挡偏差 ≈ (−4,−1) 且伤害平均 ≤2.5、≤6帧 ≥15')
