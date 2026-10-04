# -*- coding: utf-8 -*-
"""sweep_block_rule.py — 在新索敌语义下扫描"④阻挡判定"，检验 1-1 第 2 只敌人的残余。

## 背景（本轮诊断结果，`diag_enemy2_approach.py`）
模拟器中第 2 只猎狗沿"格中心→格中心"直线行进，**最接近芬 0.5 格**；
它在**帧 432 被"捕获距离 1.0"挡下并吸附到 (3,4)**，此时才进入芬的 2 格范围
⇒ 芬要到**帧 450** 才命中（标定是**帧 432**，对应索敌帧 414）。

标定则显示：**帧 432 命中、帧 443 才阻挡** ⇒ 实机在**尚未被阻挡**时就能打它。
⇒ 因此残差出在 **④阻挡**（不是 ②索敌）。本脚本扫描阻挡参数，看能否同时满足"432 命中 / 443 阻挡"。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from sweep_hit_volume import run, score     # noqa: E402


def block_frames(opts: dict, frames: int = 700) -> list[int]:
    b = run(opts)
    return [l.frame for l in b.logs if l.kind == 'block']


def hit_frames(opts: dict, frames: int = 700) -> list[tuple[int, str, str]]:
    b = run(opts)
    return [(l.frame, l.detail['src'], l.detail['tgt']) for l in b.logs if l.kind == 'hit']


print('★基准（新索敌语义 + 捕获距离 1.0 + 吸附）')
print(f'  block {block_frames({})}；芬打第 2 只 '
      f'{[f for f, s, t in hit_frames({}) if s == "芬" and t == "猎狗"]}')
print('  标定：芬命中第 2 只 = 432；阻挡 = 443\n')

print(f'{"规则":>16} {"捕获距离":>8} {"吸附":>5} {"平均":>6} {"≤6帧":>5} {"最大":>5} {"block 帧":>12}')
for cd in (1.0, 1.25, 1.4, 1.5, 1.75, 2.0):
    for snap in (True, False):
        opts = {'block_capture_distance': cd, 'block_snap': snap}
        a, h, m, _d = score(run(opts))
        print(f'{"capture_distance":>16} {cd:>8.2f} {str(snap):>5} {a:>6.2f} {h:>5} {m:>5} '
              f'{str(block_frames(opts)):>12}')
for rule, label in (('cell_3x3', '格3x3(切比雪夫)'), ('cell_3x3_round', '格3x3(圆角)'),
                    ('cell_3x3_hit', '格3x3+敌0.1圆')):
    for snap in (True, False):
        opts = {'block_rule': rule, 'block_snap': snap}
        a, h, m, _d = score(run(opts))
        print(f'{label:>16} {"—":>8} {str(snap):>5} {a:>6.2f} {h:>5} {m:>5} '
              f'{str(block_frames(opts)):>12}')
