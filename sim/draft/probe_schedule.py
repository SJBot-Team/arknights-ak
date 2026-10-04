# -*- coding: utf-8 -*-
"""probe_schedule.py — 打印某关的**完整出怪时间轴**（build_schedule 展开结果）。

用途：与视频侧（图像识别）检出的"敌人出现"时刻逐条对照 —— 这是
"未标定后半部分"的主要核验通道。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim import data as D                 # noqa: E402
from ak_sim.engine import build_schedule     # noqa: E402
from ak_sim.scenario import Scenario         # noqa: E402

stage = sys.argv[1] if len(sys.argv) > 1 else '1-1'
sc = Scenario(stage)
lv = D.load_level(sc.stage_code)
sch = build_schedule(lv)
print(f'关卡 {stage} ({sc.stage_code})  出怪动作 {len(sch)} 条')
print(f'{"t(s)":>7} {"帧":>7} {"敌人":<26} {"路线":>5} {"wave":>5} {"frag":>5}')
for a in sch:
    print(f'{a["t"]:>7.1f} {a["t"] * 30:>7.0f} {str(a["key"]):<26} {a["route"]:>5} '
          f'{a["wave"]:>5} {a["frag"]:>5}')
