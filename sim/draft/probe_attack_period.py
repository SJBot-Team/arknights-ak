# -*- coding: utf-8 -*-
"""probe_attack_period.py — ★由标定表反推实机"攻击周期"，与模拟器比对

## 依据（目标③：以事件精确帧判定模拟准确性）
上一轮逐条对照显示：**前段吻合、后段漂移** ⇒ 典型特征是"**周期量（攻击间隔/攻速）不准**"。
本脚本直接把"**周期量**"算出来两侧对比 —— 这是最能定位偏差的判定方式。

## 标定表里可直接读出两条周期
- **芬 命中猎狗pro 1**：帧 **221 / 253 / 285 / 317 / 349** ⇒ 间隔恒为 **32 帧**
- **猎狗pro 1/2 命中芬**：帧 **255 / 298 / 340** ⇒ 间隔约 **42~43 帧**

## 本脚本
1. 从标定表序列**反推实机周期**（并给出一致性检验）；
2. 从**模拟器切片**读出芬的 `atk_interval_frames`、以及实际"伤害事件"序列；
3. 对比两侧，指出偏差方向与幅度。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim.engine import Battle              # noqa: E402
from ak_sim.events import extract_events      # noqa: E402
from ak_sim.scenario import Scenario          # noqa: E402

STAGE = '1-1'
FANG, MIDN = 'char_123_fang', 'char_283_midn'
DIR_MAP = {'左': '左', '右': '右', '上': '上', '下': '下'}
DEPLOYS = [(10, FANG, 'D6', '左', 8), (411, MIDN, 'D4', '上', None)]

# 标定表：芬 命中敌 的时刻（帧）
CAL_FANG_HIT = [221, 253, 285, 317, 349]
# 标定表：敌 命中芬 的时刻（帧）
CAL_ENEMY_HIT = [255, 298, 340]


def to_rc(tile: str):
    return ord(tile[0].upper()) - 65, int(tile[1:]) - 1


def diffs(xs):
    return [b - a for a, b in zip(xs, xs[1:])]


def main():
    print('=== 一、由标定表反推实机周期 ===')
    d1 = diffs(CAL_FANG_HIT)
    d2 = diffs(CAL_ENEMY_HIT)
    print(f'  芬 命中敌  帧序列 {CAL_FANG_HIT}  间隔 {d1}')
    if d1:
        print(f'    ⇒ 实机"芬的攻击周期" = {sum(d1)/len(d1):.1f} 帧'
              f'（={sum(d1)/len(d1)/30:.3f} 秒）；一致性：{"恒定" if len(set(d1))==1 else "有波动"}')
    print(f'  敌 命中芬  帧序列 {CAL_ENEMY_HIT}  间隔 {d2}')
    if d2:
        print(f'    ⇒ 实机"猎狗pro 的攻击周期" = {sum(d2)/len(d2):.1f} 帧'
              f'（={sum(d2)/len(d2)/30:.3f} 秒）')

    print('\n=== 二、模拟器侧 ===')
    sc = Scenario(STAGE)
    b = Battle(sc.stage_code, seed=0, record=True, record_every=1, max_frames=700)
    plan = {}
    for f, char, tile, direc, cov in DEPLOYS:
        plan.setdefault(f, []).append((char, to_rc(tile), direc, cov))
    for f in range(700):
        b.tick()
        if b.frame in plan:
            for char, (r, c), direc, cov in plan[b.frame]:
                b.deploy(char, r, c, direction=DIR_MAP[direc], elite=2, level=90,
                         potential=6, trust=200, skill_index=0, skill_level=7, cost=cov)

    # 读芬的攻速相关字段
    fu = None
    for fr in b.frames:
        for u in fr.get('units', []):
            if u.get('name') == '芬':
                fu = u
                break
        if fu:
            break
    if fu:
        keys = ('name', 'atk', 'attack_speed', 'base_attack_time', 'atk_interval_frames',
                'block_cnt', 'df', 'res', 'max_hp', 'skill_charge')
        print('  模拟器芬的字段：')
        for k in keys:
            if k in fu:
                print(f'    {k} = {fu[k]}')
    else:
        print('  ★未在切片中找到芬')

    ev = extract_events(b.frames)
    dmg = [e['frame'] for e in ev if e['type'] in ('damage', 'damage_first')]
    print(f'\n  模拟器伤害事件帧：{dmg}')
    if len(dmg) >= 2:
        dd = diffs(dmg)
        print(f'  相邻间隔：{dd}')
        print(f'    ⇒ 模拟器平均"伤害事件间隔" = {sum(dd)/len(dd):.1f} 帧')

    print('\n=== 三、对比与结论 ===')
    if d1:
        real = sum(d1) / len(d1)
        print(f'  实机芬攻击周期 = {real:.1f} 帧')
        if fu and fu.get('atk_interval_frames'):
            sim = float(fu['atk_interval_frames'])
            print(f'  模拟器芬 atk_interval_frames = {sim:.2f} 帧  ⇒ 差 {sim - real:+.2f} 帧')
        if fu and fu.get('attack_speed') is not None:
            print(f'  模拟器芬 attack_speed = {fu["attack_speed"]}')
        if fu and fu.get('base_attack_time') is not None:
            print(f'  模拟器芬 base_attack_time = {fu["base_attack_time"]} 秒'
                  f'（⇒ {float(fu["base_attack_time"])*30:.1f} 帧）')


if __name__ == '__main__':
    main()
