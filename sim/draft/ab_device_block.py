# -*- coding: utf-8 -*-
"""ab_device_block.py — A/B：预置装置「是否阻挡敌人（并因此被敌人攻击）」对案例的影响。

背景冲突：
  · 用户 2026-09-14 更正：应急储备**不会被敌人攻击**，只影响寻路（我们据此把 DEVICE 从阻挡者里去掉）；
  · 但作者作战记录第 7 行在 **29.0s** 就安排「部署 弦惊」（23 费），而 rune 把上限压到 20，
    且作者自己的 `费用` 列在 20.0s 读到 20（= 仍在上限上）⇒ 上限必须在 20~29s 之间抬到 ≥23，
    唯一可能来源就是「拆掉应急储备 +5/+5」（平民 +2 要等 ≈45s 才到账）。
  · 蕾缪安射程内 96.6% 的时间都有敌人 ⇒ 按「有敌人优先打敌人」的索敌，她**永远拆不掉**储备。

本脚本对比两种装置语义下的：储备被摧毁时刻、费用上限、首条弦惊落地时刻、判负时刻。
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

BLOCK_OLD = "            if o.side != 'ALLY' or not o.alive or o.block_cnt <= 0:"
BLOCK_WITH_DEV = "            if o.side not in ('ALLY', 'DEVICE') or not o.alive or o.block_cnt <= 0:"


def set_device_block(on: bool):
    s = io.open(ENGINE, encoding='utf-8').read()
    if on:
        s = s.replace(BLOCK_OLD, BLOCK_WITH_DEV)
    else:
        s = s.replace(BLOCK_WITH_DEV, BLOCK_OLD)
    io.open(ENGINE, 'w', encoding='utf-8', newline='').write(s)


def run(tag):
    out = subprocess.run([PY, os.path.join(HERE, 'diag_cost_timeline.py')],
                         capture_output=True, text=True, encoding='utf-8', errors='replace')
    print(f'===== {tag} =====')
    for line in (out.stdout or '').splitlines():
        if any(k in line for k in ('device', '街头', 'cost_cap_up', '最终上限', '战果', '弦惊')):
            print('   ', line.strip()[:150])


set_device_block(True)
run('装置语义 B：装置阻挡敌人（⇒ 可能被敌人打死）')
set_device_block(False)
run('装置语义 A：装置只影响寻路、不被敌人攻击（用户更正，当前实现）')
