# -*- coding: utf-8 -*-
"""probe_damage_values.py — 核对敌人 hp 覆盖与伤害数值（标定"芬受伤 13→9"是关键线索）

## 标定给出的两个校验点
1. **第 2 只猎狗（enemy_1000_gopro）hp = 820** —— 本方取此值，但实机可能因**关卡覆盖**而不同；
2. **芬受伤：帧207~378 为 13，帧413 起变为 9** ——
   同一个敌人在同一场战斗中对芬的伤害从 13 降到 9 ⇒ **敌方攻击力被某种减益降低**（约 ×0.69）。
   这是**伤害公式与减益机制**的绝佳校验点。

## 本脚本
1. 打印 1-1 的 `enemyDbRefs`（含 `overwrittenData`），看第 2 只的实际 hp；
2. 打印"猎狗pro / 猎狗"的攻击力与芬的防御，**反推 13 与 9 是否与公式一致**；
3. 查"芬是否有减攻类天赋/技能"（1★先锋不太可能）⇒ 可能是**关卡的 `enemy_attribute_mul`** 或
   **其它单位（月见夜「要害瞄准」？）** 的影响。
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim import data as D            # noqa: E402
from ak_sim.scenario import Scenario    # noqa: E402

STAGE = '1-1'


def main():
    sc = Scenario(STAGE)
    lv = D.load_level(sc.stage_code)

    print('=== 一、enemyDbRefs（关卡敌人引用与覆盖）===')
    for i, ref in enumerate(lv.get('enemyDbRefs') or []):
        ov = ref.get('overwrittenData')
        print(f'  [{i}] id={ref.get("id")} level={ref.get("level")} useDb={ref.get("useDb")} '
              f'overwritten={"有" if ov else "无"}')
        if ov:
            print('       overwrittenData =', json.dumps(ov, ensure_ascii=False)[:300])

    print('\n=== 二、相关敌人的属性 ===')
    for key in ('enemy_1000_gopro', 'enemy_1000_gopro_2'):
        try:
            e = D.get_enemy(key)
        except Exception as ex:
            print(f'  [{key}] 取失败: {ex}')
            continue
        a = (e.get('attrs') or {})
        print(f'  [{key}] name={e.get("name")} hp={a.get("max_hp")} atk={a.get("atk")} '
              f'df={a.get("def")} res={a.get("res")} interval={a.get("attack_interval_frames") or a.get("base_attack_time")}')

    print('\n=== 三、芬的属性（用于反推伤害）===')
    sp = D.get_operator('char_123_fang', elite=2, level=90, potential=6, trust=200)
    a = sp.get('attrs') or {}
    print(f'  芬: hp={a.get("max_hp")} atk={a.get("atk")} df={a.get("df")} res={a.get("res")}')

    print('\n=== 四、标定校验点 ===')
    print('  标定：芬受伤 帧207~378 = 13，帧413 起 = 9（同一敌人、同一场战斗）')
    print('  ⇒ 敌方攻击力应发生约 ×0.69 的变化（13→9）')
    print('  ⇒ 需查：关卡 runes / 我方减益 / 敌人自身状态（如"被月见夜天赋降低攻击力"）')

    print('\n=== 五、关卡 runes / globalBuffs ===')
    for k in ('runes', 'optionalRunes', 'globalBuffs'):
        v = lv.get(k)
        print(f'  {k}: {json.dumps(v, ensure_ascii=False)[:300] if v else "（空）"}')

    print('\n=== 六、月见夜的天赋（「要害瞄准」是否含减益）===')
    ms = D.get_operator('char_283_midn', elite=2, level=90, potential=6, trust=200)
    for t in (ms.get('talents') or []):
        for c in (t.get('candidates') or []):
            print(f'  {c.get("name")}: {c.get("description")}')


if __name__ == '__main__':
    main()
