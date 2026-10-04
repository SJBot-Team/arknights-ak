# -*- coding: utf-8 -*-
"""probe_waves_raw.py — 打印关卡**原始** waves/fragments/actions（不展开 count），
并统计 SPAWN 动作的敌人总数，用于与游戏内 HUD 的「击破数 x/总数」对照。

★ 游戏 HUD 的"总数"是**硬地面真值**：1-1 实测 **33**。
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim import data as D                 # noqa: E402
from ak_sim.scenario import Scenario         # noqa: E402

stage = sys.argv[1] if len(sys.argv) > 1 else '1-1'
sc = Scenario(stage)
lv = D.load_level(sc.stage_code)
print('关卡', sc.stage_code)
tot = 0
for wi, w in enumerate(lv.get('waves') or []):
    print(f'wave {wi}: preDelay={w.get("preDelay")} postDelay={w.get("postDelay")} '
          f'maxTimeWaiting={w.get("maxTimeWaiting")} fragments={len(w.get("fragments") or [])}')
    for fi, fr in enumerate(w.get('fragments') or []):
        print(f'  frag {fi}: preDelay={fr.get("preDelay")} actions={len(fr.get("actions") or [])}')
        for ai, a in enumerate(fr.get('actions') or []):
            cnt = a.get('count', 1) or 1
            if a.get('actionType') == 'SPAWN':
                tot += cnt
            print(f'    act {ai}: {json.dumps(a, ensure_ascii=False)}'
                  + (f'   [×{cnt}]' if a.get('actionType') == 'SPAWN' else ''))
print(f'\n★ SPAWN 展开的敌人总数 = {tot}（游戏 HUD 地面真值：见下）')
