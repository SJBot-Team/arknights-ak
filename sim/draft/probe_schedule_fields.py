# -*- coding: utf-8 -*-
"""probe_schedule_fields.py — ★**出怪调度字段普查**（先摸底，避免重复造轮子）。

依据（知识库既有沉淀，勿重复推导）：
- 伪代码层：`knowledge/02_作战机制/24_常规关卡流程伪代码.md` §1.3/§6
- 时间轴算法：`knowledge/04/…/27_露托数据源与出怪时序本地化.md` §三.2（本库已实现）
- cpp 结构：`knowledge/04/…/33_cpp层战斗类结构与字段速查.md` §4.4 / §五
  `WaveData{preDelay, postDelay, maxTimeWaitingForNextWave, fragments, advancedWaveTag}`
  `FragmentData{preDelay, actions}`
  `ActionData{actionType, managedByScheduler, key, count, preDelay, interval, useExtraRoute,
              routeIndex, blockFragment, randomSpawnGroupKey, randomSpawnGroupPackKey,
              randomType, refreshType, weight}`
  `Scheduler{m_waveStartTime, m_fragmentStartTime, m_actionQueue, m_blockCounter,
             m_spawnedEnemiesCnt, …, FinishCurrentWave(), TrackEnemyAtNextWave()}`
- 反汇编：`knowledge/04/36…` K-021「波次：while(本波未完成 && 已等 < maxTimeWaitingForNextWave) yield；
  超时即清空该波列表」

**用途**：弄清"哪些关卡真的用到 `blockFragment` / `maxTimeWaitingForNextWave` / 随机出怪组"，
从而判断当前"静态时间轴"实现够不够，以及要先补哪一块。
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim import data as D                 # noqa: E402

LEVELS = os.path.join(D.AKGD, 'levels')

# 默认值（等于不启用该特性）
DEFAULT_RANDOM_TYPE = 'ALWAYS'
DEFAULT_REFRESH_TYPE = 'ALWAYS'


def survey(path: str, label: str) -> dict:
    lv = json.load(open(path, encoding='utf-8'))
    out = {
        'label': label,
        'waves': len(lv.get('waves') or []),
        'fragments': 0, 'actions': 0, 'spawn': 0, 'enemies': 0,
        'action_types': Counter(), 'flags': Counter(), 'random': Counter(),
        'maxTimeWaiting': [],
    }
    for w in (lv.get('waves') or []):
        out['maxTimeWaiting'].append(w.get('maxTimeWaitingForNextWave'))
        if w.get('postDelay'):
            out['flags']['wave.postDelay != 0'] += 1
        if w.get('advancedWaveTag'):
            out['flags']['wave.advancedWaveTag 非空'] += 1
        for fr in (w.get('fragments') or []):
            out['fragments'] += 1
            for a in (fr.get('actions') or []):
                out['actions'] += 1
                at = a.get('actionType')
                out['action_types'][at] += 1
                if at == 'SPAWN':
                    out['spawn'] += 1
                    out['enemies'] += int(a.get('count') or 1)
                # 非默认开关
                for k in ('managedByScheduler', 'blockFragment', 'dontBlockWave', 'useExtraRoute',
                          'forceBlockWaveInBranch', 'autoPreviewRoute', 'autoDisplayEnemyInfo',
                          'isUnharmfulAndAlwaysCountAsKilled'):
                    v = a.get(k)
                    if k == 'managedByScheduler':
                        if v is not True:
                            out['flags'][f'action.{k}={v}'] += 1
                    elif v:
                        out['flags'][f'action.{k}=True'] += 1
                for k in ('hiddenGroup', 'randomSpawnGroupKey', 'randomSpawnGroupPackKey'):
                    if a.get(k):
                        out['random'][f'{k}={a[k]}'] += 1
                if a.get('randomType') not in (None, DEFAULT_RANDOM_TYPE):
                    out['random'][f"randomType={a['randomType']}"] += 1
                if a.get('refreshType') not in (None, DEFAULT_REFRESH_TYPE):
                    out['random'][f"refreshType={a['refreshType']}"] += 1
                if int(a.get('weight') or 0) != 0:
                    out['random'][f"weight={a['weight']}"] += 1
    return out


def find_levels():
    """列出本地已入库的关卡文件（用于普查）。"""
    hits = []
    for root, _dirs, files in os.walk(LEVELS):
        for f in files:
            if f.endswith('.json'):
                hits.append(os.path.join(root, f))
    return sorted(hits)


def main():
    want = sys.argv[1:]
    files = find_levels()
    print(f'本地关卡文件 {len(files)} 个；普查 {"全部" if not want else want}\n')
    rows = []
    for p in files:
        rel = os.path.relpath(p, LEVELS).replace('\\', '/')
        if want and not any(w in rel for w in want):
            continue
        try:
            rows.append(survey(p, rel))
        except Exception as e:                       # noqa: BLE001
            print(f'  … {rel} 解析失败: {e}')
    if not rows:
        print('（无匹配关卡）')
        return
    print(f'{"关卡":<44} {"波":>3} {"片":>4} {"动作":>5} {"SPAWN":>6} {"敌":>5} '
          f'{"randomType":>10} {"blockFrag":>9} {"maxWait":>8}')
    for r in rows:
        bf = r['flags'].get('action.blockFragment=True', 0)
        rt = r['random'].get('randomType=RANDOM', 0)
        mw = [x for x in r['maxTimeWaiting'] if x]
        print(f'{r["label"]:<44} {r["waves"]:>3} {r["fragments"]:>4} {r["actions"]:>5} '
              f'{r["spawn"]:>6} {r["enemies"]:>5} {rt:>10} {bf:>9} '
              f'{(max(mw) if mw else "—"):>8}')

    print('\n★ 全部非默认标记汇总：')
    flag = Counter()
    rand = Counter()
    for r in rows:
        flag.update(r['flags'])
        rand.update(r['random'])
    for k, v in flag.most_common():
        print(f'   {k:<40} {v}')
    if not flag:
        print('   （全部动作均为默认）')
    print('★ 随机出怪相关：')
    for k, v in rand.most_common(12):
        print(f'   {k:<40} {v}')
    if not rand:
        print('   （无）')


if __name__ == '__main__':
    main()
