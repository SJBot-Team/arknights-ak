# -*- coding: utf-8 -*-
"""sweep_block_phase.py — ★扫描**阻挡扫描相位**：全局帧时钟 vs 每角色 ticker（随部署帧）。

## 依据（用户 2026-09-15 提醒）
「**阻挡扫描帧与干员部署帧高度相关，且不同干员存在差异**」
—— `m_findBlockeeTicker` 是 `Character` 上的 `PeriodicTicker`（偏移 0x380，
见 `knowledge/04/33`）⇒ **每角色独立计时**，相位由**部署时刻**决定，
而非全局 `frame % 3`。**待补**：创建时的初值与自增顺序无权威来源 ⇒ 扫描相位 0/1/2。

## 输出
各相位下：阻挡帧、偏差（标定 [236,443]）、伤害统计、芬的部署帧。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from sweep_hit_volume import run, score       # noqa: E402

CAL = [236, 443]
print(f'{"相位模式":>12} {"ticker相位":>9} {"部署帧(芬)":>10} {"阻挡帧":>12} {"偏差":>10} '
      f'{"伤害平均":>8} {"≤6":>4} {"最大":>5}')
for mode in ('global', 'per_unit'):
    for ph in (0, 1, 2):
        opts = {'block_rule': 'radius', 'block_radius': 0.7071,
                'block_scan_phase': mode, 'block_ticker_phase': ph}
        b = run(opts)
        bl = [l.frame for l in b.logs if l.kind == 'block']
        dv = (bl[0] - CAL[0], bl[1] - CAL[1]) if len(bl) >= 2 else None
        a, h, m, _ = score(b)
        dep = [l.frame for l in b.logs if l.kind in ('deploy', 'deployed')]
        star = ' ★' if dv and abs(dv[0]) <= 3 and abs(dv[1]) <= 3 else ''
        print(f'{mode:>12} {ph:>9} {str(dep[:2]):>10} {str(bl):>12} {str(dv):>10} '
              f'{a:>8.2f} {h:>4} {m:>5}{star}')
print(f'\n标定阻挡帧 = {CAL}；★ = 两偏差均 ≤3 帧')
