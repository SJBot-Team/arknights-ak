# -*- coding: utf-8 -*-
"""probe_windup_field.py — 查干员/敌人数据里的"攻击前摇"字段

## 目的
上一轮定位：**模拟器缺"攻击前摇"**（实机 ≈14 帧，模拟器 0 帧）导致"周期对、相位错"。
本脚本在数据层找出承载"前摇"的字段，为实现修正提供依据。

## 已知
`baseAttackTime`（攻击间隔）已在用 ⇒ 32 帧（芬）与实机一致。
AK 的攻击动画时间通常还有：**`attackPreDelay`**（前摇）、`attackAnimationTime`（动画时长）
等字段（位于 `character_table` 或敌人表，或技能的 blackboard 里）。
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim import data as D            # noqa: E402

FANG = 'char_123_fang'


def dump_keys(obj, prefix='', depth=0, maxd=3, seen=None):
    """递归列出字段名（含可能的 delay/animation 关键词）。"""
    if seen is None:
        seen = set()
    out = []
    if depth > maxd:
        return out
    if isinstance(obj, dict):
        for k, v in obj.items():
            path = f'{prefix}.{k}' if prefix else k
            if any(w in k.lower() for w in ('delay', 'animation', 'windup', 'wind',
                                            'pre', 'post', 'attacktime', 'duration')):
                out.append((path, v))
            out += dump_keys(v, path, depth + 1, maxd, seen)
    elif isinstance(obj, list) and obj and depth < maxd:
        out += dump_keys(obj[0], f'{prefix}[0]', depth + 1, maxd, seen)
    return out


def main():
    print('=== 一、干员表里的"时序类"字段（芬）===')
    ct = D.load_table('character_table.json')
    c = ct.get(FANG)
    if not c:
        print('  未找到芬')
        return
    print(f'  顶层键: {sorted(c.keys())}')
    for path, v in dump_keys(c)[:30]:
        print(f'    {path} = {str(v)[:90]}')

    print('\n=== 二、敌人表里的"时序类"字段（猎狗pro）===')
    for tbl in ('enemy_database.json', 'enemy_handbook_table.json'):
        try:
            et = D.load_table(tbl)
        except Exception as e:
            print(f'  [{tbl}] 读取失败: {e}')
            continue
        if not isinstance(et, dict):
            print(f'  [{tbl}] 非字典（{type(et)}）')
            continue
        # 找猎狗 pro
        hit = None
        for k, v in list(et.items()):
            if isinstance(v, dict) and 'gopro' in json.dumps(v, ensure_ascii=False)[:400]:
                hit = (k, v)
                break
        print(f'  [{tbl}] 键数 {len(et)}；示例键 {list(et.keys())[:5]}')
        if hit:
            k, v = hit
            print(f'  命中: {k}')
            for path, val in dump_keys(v)[:20]:
                print(f'    {path} = {str(val)[:90]}')

    print('\n=== 三、模拟器当前如何算攻击（源码片段）===')
    import inspect
    from ak_sim.engine import Battle
    src = inspect.getsource(Battle)
    keys = ('atk_interval', 'atk_cd', 'cd', 'windup', 'pre_delay', 'attack')
    for line in src.splitlines():
        s = line.strip()
        if any(k in s for k in keys) and ('=' in s or 'if' in s):
            print('   ', s[:110])


if __name__ == '__main__':
    main()
