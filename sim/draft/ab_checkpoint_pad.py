# -*- coding: utf-8 -*-
"""ab_checkpoint_pad.py — A/B：检查点到达宽容度 CHECKPOINT_ARRIVE_PAD 对「敌人里程/进点时刻」的影响。

假设：到达检查点的宽容度太大（0.5 格）会让敌人在**还没走到检查点**时就拐向下一段，
从而抄近路（我们的里程 13.38 格 vs 检查点折线 16.0 格），整条流水线因此偏快（§7.49 实测偏快 7s）。
"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(HERE, 'ak_sim', 'engine.py')
PY = sys.executable


def set_pad(v):
    s = io.open(ENGINE, encoding='utf-8').read()
    s = re.sub(r'CHECKPOINT_ARRIVE_PAD = [0-9.]+', f'CHECKPOINT_ARRIVE_PAD = {v}', s)
    io.open(ENGINE, 'w', encoding='utf-8', newline='').write(s)


def run():
    out = subprocess.run([PY, os.path.join(HERE, 'diag_flow_speed.py')],
                         capture_output=True, text=True, encoding='utf-8', errors='replace')
    lines = [l for l in (out.stdout or '').splitlines() if 'enemy_1010_demon' in l or 'enemy_1317' in l]
    return lines[:3]


for pad in ('0.5', '0.25', '0.05', '0.0'):
    set_pad(pad)
    print(f'--- CHECKPOINT_ARRIVE_PAD = {pad} ---')
    for l in run():
        print('   ', l.strip())
set_pad('0.5')
print('已还原 0.5')
