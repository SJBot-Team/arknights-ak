# -*- coding: utf-8 -*-
"""probe_schedule_detail.py — 对"用到非默认调度语义"的关卡做**明细**输出。

承接 `probe_schedule_fields.py` 的普查结论：
- `blockFragment=True` 只在 **1-11** 出现 1 次；
- `randomSpawnGroupKey` / `weight` 集中在某关（本脚本点名）；
- `maxTimeWaitingForNextWave` 全部 = -1（超时清场未启用）。
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim import data as D                 # noqa: E402

LEVELS = os.path.join(D.AKGD, 'levels')


def walk(rel: str):
    lv = json.load(open(os.path.join(LEVELS, rel), encoding='utf-8'))
    for wi, w in enumerate(lv.get('waves') or []):
        yield ('wave', wi, None, None, w)
        for fi, fr in enumerate(w.get('fragments') or []):
            yield ('frag', wi, fi, None, fr)
            for ai, a in enumerate(fr.get('actions') or []):
                yield ('action', wi, fi, ai, a)


def main():
    files = []
    for root, _d, fs in os.walk(LEVELS):
        for f in fs:
            if f.endswith('.json'):
                files.append(os.path.relpath(os.path.join(root, f), LEVELS).replace('\\', '/'))
    print('★ 含 randomSpawnGroup / weight 的关卡与明细：')
    for rel in sorted(files):
        rows = list(walk(rel))
        hits = [r for r in rows if r[0] == 'action'
                and (r[4].get('randomSpawnGroupKey') or int(r[4].get('weight') or 0) != 0)]
        if not hits:
            continue
        print(f'\n--- {rel}（{len(hits)} 条）---')
        for kind, wi, fi, ai, a in hits:
            print(f'  wave{wi} frag{fi} act{ai}: key={a.get("key")} count={a.get("count")} '
                  f'route={a.get("routeIndex")} preDelay={a.get("preDelay")} '
                  f'interval={a.get("interval")}')
            print(f'      randomSpawnGroupKey={a.get("randomSpawnGroupKey")} '
                  f'pack={a.get("randomSpawnGroupPackKey")} weight={a.get("weight")} '
                  f'randomType={a.get("randomType")} refreshType={a.get("refreshType")}')

    print('\n★ 含 blockFragment=True 的关卡与明细：')
    for rel in sorted(files):
        for kind, wi, fi, ai, a in walk(rel):
            if kind == 'action' and a.get('blockFragment'):
                print(f'  {rel}: wave{wi} frag{fi} act{ai} key={a.get("key")} '
                      f'count={a.get("count")} route={a.get("routeIndex")} '
                      f'preDelay={a.get("preDelay")} interval={a.get("interval")} '
                      f'managedByScheduler={a.get("managedByScheduler")}')

    print('\n★ `isUnharmfulAndAlwaysCountAsKilled=True`（"无害且恒计为击杀"）分布：')
    for rel in sorted(files):
        n = sum(1 for k, _w, _f, _a, x in walk(rel)
                if k == 'action' and x.get('isUnharmfulAndAlwaysCountAsKilled'))
        if n:
            print(f'  {rel}: {n} 条')


if __name__ == '__main__':
    main()
