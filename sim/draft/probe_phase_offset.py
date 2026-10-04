# -*- coding: utf-8 -*-
"""probe_phase_offset.py — ★定位"13 帧相位偏移"的出处

## 上一轮结论
- **模拟器攻击周期正确**（32.00 帧 vs 实机 32.0 帧，差 0）；
- **但"首次攻击的相位"整体后移 13 帧**（实机首击 221，模拟器 234）。

## 本脚本要回答
1. 模拟器切片里有哪些可用于追踪"攻击时机"的字段（冷却/前摇等）；
2. **敌人何时进入芬的攻击范围**（逐帧记录敌人与芬的格距）；
3. **芬首次"真正造成伤害"的帧**，与标定"帧 207 进入攻击前摇 / 帧 221 命中"比对；
4. 由"敌人进入范围"到"首次命中"的帧数，与实机的对应量对比 ⇒ 判断 13 帧出在"到位"还是"起手"。
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim.engine import Battle              # noqa: E402
from ak_sim.scenario import Scenario          # noqa: E402

STAGE = '1-1'
FANG = 'char_123_fang'
DIR_MAP = {'左': '左'}

# 标定：芬 @D6（=row3,col5）朝左；部署帧 10
FANG_RC = (3, 5)


def main():
    sc = Scenario(STAGE)
    b = Battle(sc.stage_code, seed=0, record=True, record_every=1, max_frames=700)
    for f in range(700):
        b.tick()
        if b.frame == 10:
            b.deploy(FANG, *FANG_RC, direction='左', elite=2, level=90,
                     potential=6, trust=200, skill_index=0, skill_level=7, cost=8)

    # ① 单位字段清单（取一帧里有单位的数据）
    sample = None
    for fr in b.frames:
        us = fr.get('units') or []
        if us:
            sample = us[0]
            break
    print('=== 一、切片中的单位字段 ===')
    if sample:
        for k, v in sorted(sample.items()):
            s = str(v)
            print(f'  {k} = {s[:70]}')
    else:
        print('  （未找到单位）')

    # ② 逐帧记录：敌人位置、到芬的距离、芬的字段
    print('\n=== 二、逐帧追踪（帧 10~260，仅打印变化点）===')
    prev = None
    for fr in b.frames:
        f = fr['f']
        if f < 10 or f > 260:
            continue
        enemies = [u for u in (fr.get('units') or []) if not u.get('is_operator')]
        me = [u for u in (fr.get('units') or []) if u.get('name') == '芬']
        row = []
        for e in enemies:
            row.append((e.get('name'), e.get('pos') or e.get('rc'), e.get('hp')))
        key = json.dumps(row, ensure_ascii=False, default=str)
        if key != prev:
            extra = ''
            if me:
                m = me[0]
                extra = (f'  芬 pos={m.get("pos") or m.get("rc")} hp={m.get("hp")} '
                         f'skill_charge={m.get("skill_charge")}')
            print(f'  帧 {f:>3}: 敌 {key}{extra}')
            prev = key

    # ③ 首次伤害帧
    from ak_sim.events import extract_events
    ev = extract_events(b.frames)
    dmg = [e for e in ev if e['type'] in ('damage', 'damage_first')]
    print(f'\n=== 三、伤害事件（前 8 条）===')
    for e in dmg[:8]:
        print(f'  帧 {e["frame"]:>3}: {e["type"]}  {json.dumps({k: v for k, v in e.items() if k not in ("frame","type")}, ensure_ascii=False, default=str)[:110]}')
    print('\n对照：标定「帧 207 芬 进入攻击前摇」「帧 221 芬首次命中」')


if __name__ == '__main__':
    main()
