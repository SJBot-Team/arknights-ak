# -*- coding: utf-8 -*-
"""smoke_test.py — 冒烟测试：1-7 部署干员打怪，检查核心链路。

运行：python ak_sim/smoke_test.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim.engine import Battle
from ak_sim import fp


def main():
    b = Battle('obt/main/level_main_01-07', seed=1234)
    print(f'关卡 {b.level_id}: 地图 {b.map.height}x{b.map.width} 路线 {len(b.routes)} 波次动作 {len(b.schedule)}')
    print(f'初始费用 {b.cost} 上限 {b.cost_max} 生命 {b.life} 随机种子 {b.random_seed}')
    # 案例干员位置类型
    from ak_sim.data import get_operator
    for cid in ('char_2023_ling', 'char_4193_lemuen', 'char_1029_yato2', 'char_4091_ulika'):
        s = get_operator(cid, elite=2, level=90)
        print(f'  {s["name"]:<8} {cid:<20} position={s["position"]:<7} cost={s["attrs"]["cost"]:.0f} '
              f'block={s["attrs"]["blockCnt"]:.0f} interval={s["attrs"]["baseAttackTime"]:.2f}s range={s["rangeId"]}')
    # 部署近战干员到近战位（贴近敌径）
    spots = [(r, c) for r in range(b.map.height) for c in range(b.map.width)
             if b.map.can_deploy(r, c, melee=True)]
    print('可部署近战位数量:', len(spots), '样例:', spots[:5])
    deployed = []
    for (r, c) in spots[:4]:
        u = b.deploy('char_1029_yato2', r, c, '右')
        if u:
            deployed.append(u)
            print(f'部署 {u.name} @ ({r},{c}) HP={u.hp} ATK={u.atk} 间隔={u.attack_interval_frames}帧')
    b.run(max_frames=30 * 90)
    print(f'运行 {b.frame} 帧（{b.frame/fp.FPS:.1f}s） 结果={b.result} 剩余生命={b.life}')
    kills = [l for l in b.logs if l.kind == 'kill']
    esc = [l for l in b.logs if l.kind == 'escape']
    hits = [l for l in b.logs if l.kind == 'hit']
    blocks = [l for l in b.logs if l.kind == 'block']
    print(f'命中 {len(hits)} 击杀 {len(kills)} 阻挡 {len(blocks)} 漏怪 {len(esc)}；逐帧切片 {len(b.frames)} 帧')
    for lg in (hits[:5] + kills[:3]):
        print(f'  f={lg.frame:<5} {lg.kind:<6} {lg.detail}')
    if b.frames:
        f = b.frames[-1]
        print('末帧切片:', {'f': f['f'], 'cost': f['cost'], 'life': f['life'], 'units': len(f['units'])})
        u0 = f['units'][0] if f['units'] else None
        print('单位切片样例:', u0)


if __name__ == '__main__':
    main()
