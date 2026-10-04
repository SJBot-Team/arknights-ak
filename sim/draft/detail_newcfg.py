# -*- coding: utf-8 -*-
"""detail_newcfg.py — ★打印"新配置"（margin 0.1 + 不吸附 + 猎狗受击半径 0.8）下的**逐条偏差**。

新配置依据（第105轮突破）：客户端 prefab 的逐敌受击半径不同（分布 0.1/0.5/1.0/…），
而 1-1 的「猎狗」实测反推 ≈0.8、「猎狗pro」=0.1 ⇒ 同时满足阻挡帧与伤害帧。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from sweep_hit_volume import run, score, MAP      # noqa: E402

NEW = {'block_cell_margin': 0.1, 'block_snap': False,
       'hit_radius_by_key': {'enemy_1000_gopro': 0.8}}
OLD = {}


def table(opts, title):
    print(f'=== {title} ===')
    b = run(opts)
    a, h, m, devs = score(b)
    print(f'  伤害/出生/击杀：平均 {a:.2f} 帧、≤6 帧 {h}、最大 {m}')
    bl = [l.frame for l in b.logs if l.kind == 'block']
    print(f'  阻挡帧：{bl}（标定 [236, 443]）')
    return b


b_new = table(NEW, '新配置 margin0.1 + 不吸附 + 猎狗半径0.8')
b_old = table(OLD, '旧默认 margin1.0 + 吸附 + 一律0.1')
print()
if __name__ == '__main__' and False:
    pass
