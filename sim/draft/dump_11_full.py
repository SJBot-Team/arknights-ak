# -*- coding: utf-8 -*-
"""dump_11_full.py — 跑完 1-1 的完整时间线（与视频轴同长度），输出**全部事件**供与视频比对。

复刻（与标定表一致）：
- 游戏帧 **10**：部署 芬 `char_123_fang` @ **D6**=(row3,col5) 朝左，费用 **8**
- 游戏帧 **411**：部署 月见夜 `char_283_midn` @ **D4**=(row3,col3) 朝上，费用 **14**
- 帧数跑到 **1510**（视频轴末端的游戏帧 ≈1506）

★技能回费：芬的技能 `skcom_charge_cost[1]`（冲锋号令·α型，**等级 7**：
  `spCost=25 / initSp=6 / increment=1.0/s / cost=+6`）由**视频侧图像识别独立验证**：
  第 1 次发动在游戏帧 **581**（预测 10+19*30=580）、第 2 次在 **1333**（预测 1330）。
  本脚本可选地把"技能回费"也打进事件表，方便与视频对照。
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim.engine import Battle              # noqa: E402
from ak_sim.events import extract_events      # noqa: E402
from ak_sim.scenario import Scenario          # noqa: E402

STAGE = '1-1'
FANG, MIDN = 'char_123_fang', 'char_283_midn'
DIR_MAP = {'左': '左', '上': '上'}
DEPLOYS = [(10, FANG, 'D6', '左', 8), (411, MIDN, 'D4', '上', None)]
FRAMES = 1510


def to_rc(tile):
    return ord(tile[0]) - 65, int(tile[1:]) - 1


def main():
    sc = Scenario(STAGE)
    b = Battle(sc.stage_code, seed=0, record=True, record_every=1, max_frames=FRAMES)
    plan = {}
    for f, char, tile, direc, cov in DEPLOYS:
        plan.setdefault(f, []).append((char, to_rc(tile), direc, cov))
    for _ in range(FRAMES):
        b.tick()
        if b.frame in plan:
            for char, (r, c), direc, cov in plan[b.frame]:
                b.deploy(char, r, c, direction=DIR_MAP[direc], elite=2, level=90,
                         potential=6, trust=200, skill_index=0, skill_level=7, cost=cov)

    ev = extract_events(b.frames)
    order, n = {}, 0
    for e in sorted((x for x in ev if x['type'] == 'spawn'), key=lambda z: z['frame']):
        if str(e.get('name') or '') in ('芬', '月见夜', '令', '蕾缪安'):
            continue
        n += 1
        order[e.get('uid')] = n
    idx_name = {}
    for e in ev:
        if e['type'] == 'spawn' and e.get('uid') in order:
            idx_name[order[e['uid']]] = str(e.get('name'))

    print(f'关卡 {sc.stage_code}  模拟 {FRAMES} 帧（{FRAMES / 30:.1f} 秒游戏时间）')
    print(f'敌方总数 {n}；出现顺序（前 12）: '
          + ', '.join(f'#{k}={v}' for k, v in sorted(idx_name.items())[:12]))
    print()
    print(f'{"帧":>6} {"时间":>7} {"类型":>13} {"受害者":>10} {"攻击者":>10} {"伤害":>5}')
    print('-' * 62)
    for e in sorted(ev, key=lambda z: (z['frame'], z['type'])):
        t = e['type']
        if t in ('tick',):
            continue
        nm = str(e.get('name') or '')
        if t == 'spawn' and e.get('uid') in order:
            nm = f'{nm}(#{order[e["uid"]]})'
        src = str(e.get('src') or '-')
        dmg = e.get('dmg') or e.get('value') or ''
        print(f'{e["frame"]:>6} {e["frame"] / 30:>7.2f} {t:>13} {nm:>10} {src:>10} {str(dmg):>5}')

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       '..', '..', '.tmp', 'sim11_full_events.json')
    out = os.path.abspath(out)
    json.dump({'frames': FRAMES, 'events': ev, 'order': order}, open(out, 'w', encoding='utf-8'),
              ensure_ascii=False, default=str)
    print(f'\n事件已存 {out}')


if __name__ == '__main__':
    main()
