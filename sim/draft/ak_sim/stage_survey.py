# -*- coding: utf-8 -*-
"""stage_survey.py — **批量关卡探明台账**：一次把多个关卡的"关卡-关联单位-关联机制"探明并落盘

## 依用户"方向性修正 1"与需求"预置验证定位"
> 关卡-关联单位-关联机制一次探明…搭建时就做好与已有知识的验证定位工作，便于后续检查问题和进一步优化。

产出：
  · `.tmp/stage_survey.json` —— 结构化台账（供程序调用）
  · `.tmp/stage_survey.md`   —— 可读对照表（供人工核对）

用法：python ak_sim/stage_survey.py [关卡名...]
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim.scenario import Scenario                 # noqa: E402

TMP = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'
DEFAULT = ['1-1', '1-7', '2-1', '4-4', '7-4', '12-4', 'H12-4', 'H15-4']


def main():
    stages = sys.argv[1:] or DEFAULT
    rows, ok_n = [], 0
    for s in stages:
        try:
            sc = Scenario(s)
            d = sc.discover()
            rows.append(d)
            ok_n += 1
            print(f'  ✓ {s:<7} {d["stage_code"]:<34} 生命={d["max_life"]} 地图={d["map_rows"]}x{d["map_cols"]} '
                  f'路线={d["route_count"]} 敌人={len(d["enemy_refs"])} 出怪={len(d["spawn_actions"])} '
                  f'机制={len(d["runes"])} seed={d["random_seed"]}')
        except Exception as e:
            print(f'  ✗ {s:<7} 失败: {type(e).__name__}: {e}')
            rows.append({'stage': s, 'error': f'{type(e).__name__}: {e}'})

    os.makedirs(TMP, exist_ok=True)
    jp = os.path.join(TMP, 'stage_survey.json')
    json.dump(rows, open(jp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    L = ['# 关卡探明台账（关卡-关联单位-关联机制一次探明）', '',
         f'共 {len(rows)} 关，成功 {ok_n}', '',
         '| 关卡 | 内部目录 | 生命 | 地图 | 路线 | 敌人种类 | 出怪动作 | 机制(runes) | randomSeed |',
         '|---|---|---|---|---|---|---|---|---|']
    for d in rows:
        if 'error' in d:
            L.append(f'| {d["stage"]} | 加载失败 | | | | | | | {d["error"][:40]} |')
            continue
        runes = ', '.join(r['key'] for r in d['runes'][:4])
        L.append(f'| {d["stage"]} | `{d["stage_code"]}` | {d["max_life"]} | {d["map_rows"]}×{d["map_cols"]} | '
                 f'{d["route_count"]} | {len(d["enemy_refs"])} | {len(d["spawn_actions"])} | '
                 f'{runes} | {d["random_seed"]} |')
    L += ['', '## 各关机制的 blackboard 明细', '']
    for d in rows:
        if 'error' in d or not d.get('runes'):
            continue
        L.append(f'### {d["stage"]}（`{d["stage_code"]}`）')
        for r in d['runes']:
            L.append(f"- `{r['key']}`: {json.dumps(r['blackboard'], ensure_ascii=False)[:220]}")
        L.append('')
    mp = os.path.join(TMP, 'stage_survey.md')
    open(mp, 'w', encoding='utf-8').write('\n'.join(L))
    print(f'\n台账已写出:\n  {jp}\n  {mp}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
