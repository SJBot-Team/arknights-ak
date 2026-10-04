# -*- coding: utf-8 -*-
"""probe_spawns.py — 核对 1-1 的出怪表（数量/时刻/key/位置）与标定对齐

## 背景（上一轮发现）
模拟器中"猎狗"相关伤害事件的**受害者 uid 恒为 2**（`enemy_1000_gopro_2`），
而标定表出现的是「猎狗pro 1」（帧94 影子）与「猎狗pro 2」（帧367 影子）**两只**
⇒ 需核对：**1-1 到底该出几只猎狗、何时出、各是什么 key**。

## 本脚本
1. 解析 `waves[].fragments[].actions[]` 的全部 SPAWN：
   `(wave, fragment, action, 时刻(preDelay 等), key, 位置)`;
2. 换算为**帧号**并与标定对照（标定：帧 94 出现影子、帧 367 出现影子）；
3. 打印模拟器实际 `spawn` 事件的帧与 key，做三方对照。
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim import data as D            # noqa: E402
from ak_sim.engine import Battle        # noqa: E402
from ak_sim.events import extract_events  # noqa: E402
from ak_sim.scenario import Scenario    # noqa: E402


def main():
    sc = Scenario('1-1')
    lv = D.load_level(sc.stage_code)
    print('=== 一、1-1 的 waves / fragments / actions（SPAWN）===')
    total = 0
    t0 = None
    for wi, w in enumerate(lv.get('waves') or []):
        for fi, fr in enumerate(w.get('fragments') or []):
            for a in fr.get('actions') or []:
                if a.get('actionType') != 'SPAWN':
                    continue
                total += 1
                key = a.get('key')
                pre = a.get('preDelay', 0)
                # AK 的 fragments 有 preDelay，action 有 preDelay；这里都打出来
                print(f'  wave{wi} frag{fi}: key={key} preDelay={pre} '
                      f'action={json.dumps({k: v for k, v in a.items() if k != "key"}, ensure_ascii=False)[:150]}')
    print(f'  ⇒ SPAWN 总数 = {total}')

    print('\n=== 二、fragment 级时序（换算帧号）===')
    for wi, w in enumerate(lv.get('waves') or []):
        print(f'  wave{wi}: preDelay={w.get("preDelay")} time={w.get("time")} '
              f'maxTime={w.get("maxTime")} fragments={len(w.get("fragments") or [])}')
        for fi, fr in enumerate(w.get('fragments') or []):
            pre = fr.get('preDelay', 0 )
            try:
                fnum = round(float(pre) * 30)
            except Exception:
                fnum = None
            print(f'    frag{fi}: preDelay={pre} ⇒ 帧 {fnum}；actions={len(fr.get("actions") or [])}')

    print('\n=== 三、模拟器实际 spawn 事件 ===')
    b = Battle(sc.stage_code, seed=0, record=True, record_every=1, max_frames=700)
    for f in range(700):
        b.tick()
    ev = extract_events(b.frames)
    for e in ev:
        if e['type'] == 'spawn':
            print(f'  帧 {e["frame"]:>4}: {json.dumps({k: v for k, v in e.items() if k != "type"}, ensure_ascii=False, default=str)[:130]}')

    print('\n=== 四、与标定对照 ===')
    print('  标定：帧 94「猎狗pro 1 出现影子」、帧 367「猎狗pro 2 出现影子」')
    print('  ⇒ 应有两波出怪，且 key 应分别为 pro 与其变体')


if __name__ == '__main__':
    main()
