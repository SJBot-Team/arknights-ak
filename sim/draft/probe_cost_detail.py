# -*- coding: utf-8 -*-
"""probe_cost_detail.py — 查芬/月见夜的真实费用（attrs.cost）与潜能影响 + 费用相位"""
from __future__ import annotations

import inspect
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim import data as D            # noqa: E402

FANG, MIDN = 'char_123_fang', 'char_283_midn'


def main():
    print('=== 一、character_table 里的原始费用字段 ===')
    ct = D.load_table('character_table.json')
    for cid in (FANG, MIDN):
        c = ct[cid]
        print(f'  {cid}  name={c.get("name")}')
        for ph in (c.get('phases') or []):
            print(f'     phase {ph.get("phase")}: cost={ph.get("cost")} '
                  f'（存在 phases 内的 cost 字段：{[k for k in ph if "cost" in k.lower()]}）')
        # 潜能
        pot = c.get('potentialRanks') or []
        for i, p in enumerate(pot):
            print(f'     潜能{i}: {json.dumps(p, ensure_ascii=False)[:120]}')

    print('\n=== 二、data.get_operator 返回的 attrs.cost（各潜能）===')
    for cid in (FANG, MIDN):
        for p in range(0, 7):
            try:
                spec = D.get_operator(cid, elite=2, level=90, potential=p, trust=200)
                print(f'  {cid} 潜能{p}: attrs.cost = {spec["attrs"].get("cost")}')
            except Exception as e:
                print(f'  {cid} 潜能{p}: 失败 {e}')

    print('\n=== 三、费用增长的相位（不部署，看第 1 次 +1 的帧）===')
    from ak_sim.engine import Battle
    from ak_sim.scenario import Scenario
    b = Battle(Scenario('1-1').stage_code, seed=0, record=True, max_frames=200)
    prev = None
    for f in range(70):
        b.tick()
        if prev is not None and b.cost != prev:
            print(f'  ★ 费用 {prev:g} → {b.cost:g} 发生在帧 {b.frame}（第 {b.frame//30} 秒 第 {b.frame%30} 帧）')
        prev = b.cost

    print('\n=== 四、deploy 内部如何取 need（源码）===')
    src = inspect.getsource(Battle.deploy)
    keep = False
    for line in src.splitlines():
        if 'need =' in line or 'spec[' in line or 'cost' in line:
            print('   ', line.strip()[:110])


if __name__ == '__main__':
    main()
