# -*- coding: utf-8 -*-
"""events.py — **事件帧提取与比对框架**（需求 1.5"预置验证定位" + 用户的事件帧判定口径）

## 依用户口径
> 工程的准确性通过对照实际或视频中**事件发生的精确帧**来判定。例如：目标在这一帧血条长度被记录，
> 费用条变化一次后血条长度变化，说明目标在变化后的这一帧结算了受到的伤害。

## 提供三个能力
1. `extract_events(frames)`：从逐帧切片里**导出统一的事件时间线** ——
   出生 / 首次受伤 / 掉血 / 击杀 / 漏怪 / 费用变化 / 上限突破 / 技能开启 / 部署 / 撤退；
2. `compare_events(sim_events, ref_events, tol=0)`：把模拟事件与**参考事件**（来自视频识别或
   用户手工标记的精确帧）**逐条对齐**，输出"匹配 / 帧差 / 缺失 / 多余"；
3. `to_reference_format(events)`：导出便于手工填写的参考事件表（CSV/JSON），供用户标记真实帧。

## 事件帧约定
统一用**逻辑帧号**（1 秒 = 30 帧），同时给出秒。
"""
from __future__ import annotations

import json
import os
import sys

FPS = 30


def extract_events(frames: list) -> list:
    """从逐帧切片导出事件时间线（按帧号排序）。"""
    ev = []
    prev_hp: dict[int, int] = {}
    seen: set[int] = set()
    prev_cost = None
    prev_units: set[int] = set()
    last_seen: dict = {}          # uid -> {'key','name'}，供 despawn 事件补名
    for fr in frames:
        f = fr.get('f')
        # 单位相关事件
        cur_ids = set()
        for u in (fr.get('units') or []):
            uid = u['uid']
            cur_ids.add(uid)
            if uid not in seen:
                seen.add(uid)
                ev.append({'frame': f, 't': round(f / FPS, 3), 'type': 'spawn',
                           'uid': uid, 'key': u.get('key'), 'name': u.get('name'),
                           'hp': u.get('hp'), 'x': u.get('x'), 'y': u.get('y')})
            hp = u.get('hp')
            if uid in prev_hp and hp is not None and prev_hp[uid] != hp:
                dmg = prev_hp[uid] - hp
                # ★补"攻击者"：从本帧的 `hit` 日志里找"目标名与受害者一致"的那条，取 `src`。
                #   必要性：同一目标可能被多个单位打（如 1-1 中芬与月见夜都可能打同一只猎狗），
                #   只有受害者信息无法区分是谁打的（曾导致"月见夜的命中"被错配到"芬的命中"）。
                src_name = None
                tgt_names = str(u.get('name') or '')
                for o in (fr.get('ops') or []):
                    # ★切片的 ops 元素结构为 `{'kind': 'hit', 'detail': {'src','tgt','dmg',...}}`
                    if str(o.get('kind') or o.get('type') or '') != 'hit':
                        continue
                    payload = o.get('detail') or o.get('data') or o
                    tn = str(payload.get('tgt') or '')
                    if tn and (tn in tgt_names or tgt_names in tn):
                        src_name = payload.get('src')
                        break
                ev.append({'frame': f, 't': round(f / FPS, 3),
                           'type': 'damage_first' if prev_hp[uid] == u.get('max_hp') else 'damage',
                           'uid': uid, 'key': u.get('key'), 'name': u.get('name'),
                           'src': src_name,
                           'dmg': dmg, 'hp': hp, 'hp_before': prev_hp[uid]})
            if hp is not None:
                prev_hp[uid] = hp
            last_seen[uid] = {'key': u.get('key'), 'name': u.get('name')}
        # 消失（击杀 / 漏怪）：区分方式看该帧的 ops 或状态
        gone = prev_units - cur_ids
        for uid in gone:
            # ★补 name/key：`kill`/`despawn` 需要"是谁死了"才能与标定表的"击杀"事件对齐
            info = last_seen.get(uid) or {}
            ev.append({'frame': f, 't': round(f / FPS, 3), 'type': 'despawn', 'uid': uid,
                       'key': info.get('key'), 'name': info.get('name')})
        prev_units = cur_ids
        # 费用
        c = fr.get('cost')
        if prev_cost is not None and c is not None and c != prev_cost:
            d = round(c - prev_cost, 4)
            ev.append({'frame': f, 't': round(f / FPS, 3),
                       'type': 'cost_up' if d > 0 else 'cost_spend',
                       'delta': d, 'cost': c})
        if c is not None:
            prev_cost = c
        # ops（部署/技能/撤退/上限突破等由引擎记的语义事件）
        for o in (fr.get('ops') or []):
            k = o.get('kind')
            if k in ('deploy', 'retreat', 'skill', 'cost_cap_up', 'life_change',
                     'civilian_arrived', 'escape', 'death', 'kill'):
                ev.append({'frame': f, 't': round(f / FPS, 3), 'type': k,
                           'detail': o.get('detail')})
            # ★2026-09-29（T-200c）：把"阻挡"与"索敌/进入前摇"也导成事件
            #   目的：标定表里有「芬 阻挡」「进入攻击前摇」两类事件，而模拟器原先不发
            #   ⇒ 逐帧审计里这 3 条永远配不上（见 `04/73 §3`）。
            elif k == 'block':
                det = o.get('detail') or {}
                ev.append({'frame': f, 't': round(f / FPS, 3), 'type': 'block',
                           'name': det.get('enemy'), 'src': det.get('by'),
                           'detail': det})
            elif k == 'target_select':
                det = o.get('detail') or {}
                ev.append({'frame': f, 't': round(f / FPS, 3), 'type': 'windup',
                           'name': det.get('src') or det.get('unit'),
                           'src': det.get('src') or det.get('unit'),
                           'detail': det})
    ev.sort(key=lambda e: (e['frame'], e['type']))
    return ev


def summarize(events: list) -> dict:
    out: dict[str, int] = {}
    for e in events:
        out[e['type']] = out.get(e['type'], 0) + 1
    return out


def compare_events(sim: list, ref: list, tol: int = 0, key_fields=('uid', 'key')) -> dict:
    """把模拟事件与参考事件逐条对齐。

    sim / ref：事件 dict 列表，至少含 `frame` 与 `type`；可含 `key`（单位）用于配对。
    tol：允许的帧差（0 = 精确同帧）。
    返回：{'matched': [...], 'missing': [...], 'extra': [...], 'max_diff': int}
    """
    def sig(e):
        return (e.get('type'), e.get('key') or e.get('name') or '')
    used = set()
    matched, missing = [], []
    for r in sorted(ref, key=lambda z: z['frame']):
        best, bestd = None, None
        for i, s in enumerate(sim):
            if i in used or sig(s) != sig(r):
                continue
            d = abs(s['frame'] - r['frame'])
            if bestd is None or d < bestd:
                best, bestd = i, d
        if best is not None and bestd is not None and bestd <= tol:
            used.add(best)
            matched.append({'type': r['type'], 'key': r.get('key'), 'ref_frame': r['frame'],
                            'sim_frame': sim[best]['frame'], 'diff': sim[best]['frame'] - r['frame']})
        else:
            missing.append(r)
    extra = [s for i, s in enumerate(sim) if i not in used]
    diffs = [abs(m['diff']) for m in matched]
    return {'matched': matched, 'missing': missing, 'extra': extra,
            'max_diff': max(diffs) if diffs else None,
            'n_ref': len(ref), 'n_sim': len(sim), 'n_matched': len(matched)}


def to_reference_format(events: list, path: str) -> str:
    """导出"参考事件表"（供用户/视频识别填写真实帧）。"""
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    rows = [{'frame': e['frame'], 't': round(e['frame'] / FPS, 3), 'type': e['type'],
             'key': e.get('key', ''), 'note': ''} for e in events]
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    return path


if __name__ == '__main__':
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.stdout.reconfigure(encoding='utf-8')
    from ak_sim.engine import Battle
    from ak_sim.scenario import Scenario
    stage = sys.argv[1] if len(sys.argv) > 1 else '1-1'
    level_id = stage if '/' in stage else Scenario(stage).stage_code
    b = Battle(level_id, seed=0, record=True)
    for _ in range(1800):
        b.tick()
        if getattr(b, 'life', None) is not None and b.life <= 0:
            break
    ev = extract_events(b.frames)
    print(f'=== {stage} 事件时间线（共 {len(ev)} 条，帧数 {len(b.frames)}）===')
    print('  类型统计:', summarize(ev))
    for e in ev[:18]:
        print('   ', json.dumps(e, ensure_ascii=False)[:150])
    out = to_reference_format(ev, os.path.join(r'C:\Users\23922\Documents\ds_harness\ak\.tmp',
                                               f'ref_events_{stage}.json'))
    print('  参考事件表已导出:', out)
