# -*- coding: utf-8 -*-
"""replay_11calib.py — **1-1 标定对局前半部分复刻**（用户工作流第 1、2 步）

## 工作流（用户指定）
1. **复刻前半部分**：按标定表在模拟环境复现事件，检验模拟环境准确性；
2. **观察效率**：报告模拟环境的计算效率；
3. **比对后半部分**：稍后用图像识别比对视频未标定部分（另脚本）。

## 标定表（用户提供）
列：`秒 | 该秒初始费用 | 帧 | 费用变化 | 操作 | 格子 | 单位 | 方向 | 动画层`
- **帧号 = 秒×30 + 帧**
- 关键操作：**部署 芬 @D6 朝左（帧10）**、**部署 月见夜 @D4 朝上（帧411）**、**芬技能自动开启（帧551）**

## 坐标映射（本轮确定）
**`row_sim = 总行数 − 显示行号`**、`col_sim = 列字母 − 'A'`
（验证：D6→row1 近战可部署 ✓、D4→row3 近战可部署 ✓、D1→row6 墙 ✓、G5→row2 高台 ✓）
"""
from __future__ import annotations

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim.engine import Battle              # noqa: E402
from ak_sim.events import extract_events      # noqa: E402
from ak_sim.scenario import Scenario          # noqa: E402

STAGE = '1-1'
# 认到的干员
FANG = 'char_123_fang'      # 芬（先锋/近战）
MIDN = 'char_283_midn'      # 月见夜（近卫/近战）
# 标定：部署操作（帧, 干员, 显示格, 方向, 标定费用覆盖）
#   ★芬：数据表满潜为 9，但标定表现场为 8（标定表自洽：10−8+3=5）
#     ⇒ 用 `cost=8` 覆盖以对齐实机；月见夜满潜 14 与标定一致，无需覆盖。
DEPLOYS = [
    (10, FANG, 'D6', '左', 8),
    (411, MIDN, 'D4', '上', None),
]
SKILL = (551, FANG, '技能自动开启')
# 标定的动画层事件（帧, 单位, 说明）——用于与模拟器对照
CALIB_ANIM = [
    (94, '猎狗pro 1', '出现影子'),
    (207, '芬', '进入攻击前摇'),
    (221, '猎狗pro 1', '芬 命中'),
    (236, '猎狗pro 1', '芬 阻挡'),
    (253, '猎狗pro 1', '芬命中'),
    (255, '芬', '猎狗pro 1 命中'),
    (285, '猎狗pro 1', '芬 命中'),
    (298, '芬', '猎狗pro 1 命中'),
    (317, '猎狗pro 1', '芬 命中'),
    (340, '芬', '猎狗pro 1 命中'),
    (349, '猎狗pro 1', '芬 命中'),
    (367, '猎狗pro 2', '出现影子'),
    (381, '猎狗pro 1', '芬 击杀'),
    (432, '猎狗pro 2', '芬 命中'),
    (438, '猎狗pro 2', '月见夜 远程命中'),
    (443, '猎狗pro 2', '芬 阻挡'),
    (461, '芬', '猎狗pro 2 命中'),
    (464, '猎狗pro 2', '芬 击杀'),
]
# 标定的费用（秒 → 该秒初始费用）
CALIB_COST = {0: 10, 3: 5, 6: 8, 7: 9, 8: 10, 9: 11, 10: 12, 11: 13, 12: 14,
              13: 15, 14: 3, 15: 4, 18: 7}
DIR_MAP = {'左': '左', '右': '右', '上': '上', '下': '下',
           'LEFT': '左', 'RIGHT': '右', 'UP': '上', 'DOWN': '下'}


def to_rc(tile: str, rows: int):
    """显示格（如 D6）→ 模拟器 (row, col)。

    ★映射规则（本轮实测确定，与 h12-4 的"令 C12 → (r2,c11)"一致）：
        row = 字母序号 − 1     （A=0, B=1, C=2, D=3 …）
        col = 数字 − 1
    验证：D6→(3,5) 第4行 col5=`.`（近战可部署 ✓）；D4→(3,3) 已实测部署成功 ✓；
          D1→(3,0)=`#`（敌人生成点）；G5→(6,4) 第7行=`#`（敌人生成点）。
    """
    row = ord(tile[0].upper()) - 65      # A→0
    col = int(tile[1:]) - 1
    return row, col


def main():
    t0 = time.time()
    sc = Scenario(STAGE)
    lv = sc.discover()
    rows = lv['map_rows']
    print(f'=== 关卡 {STAGE} ({sc.stage_code})  {lv["map_rows"]}×{lv["map_cols"]} ===')
    print(f'  初始费用={lv["initial_cost"]}  生命={lv["max_life"]}  上限(ceil)={lv["max_cost_ceil"]}')

    b = Battle(sc.stage_code, seed=0, record=True, record_every=1, max_frames=1200)
    print(f'  模拟器初始化耗时 {time.time()-t0:.2f}s')

    # ---- 复刻：按帧推进，在指定帧执行操作 ----
    t1 = time.time()
    plan = {}
    for f, char, tile, direc, cov in DEPLOYS:
        rc = to_rc(tile, rows)
        plan.setdefault(f, []).append(('deploy', char, rc, direc, cov))
    print('\n=== 复刻计划 ===')
    for f, ops in sorted(plan.items()):
        for kind, char, rc, direc, cov in ops:
            print(f'  帧 {f:>4} ({f/30:>6.2f}s): {kind} {char} @{rc} 朝{direc}'
                  + (f' 费用覆盖={cov}' if cov else ''))
    print(f'  帧 {SKILL[0]:>4} ({SKILL[0]/30:>6.2f}s): {SKILL[1]} {SKILL[2]}')

    results = []
    for f in range(0, 1200):
        b.tick()
        if b.frame in plan:
            for kind, char, (r, c), direc, cov in plan[b.frame]:
                u = b.deploy(char, r, c, direction=DIR_MAP.get(direc, '右'),
                             elite=2, level=90, potential=6, trust=200,
                             skill_index=0, skill_level=7, cost=cov)
                results.append((b.frame, char, (r, c), direc, bool(u), b.cost))
                print(f'  ▶ 帧 {b.frame}：部署 {char} @({r},{c}) 朝{direc} ⇒ '
                      f'{"成功" if u else "失败"}，费用={b.cost:.1f}')
        if f >= 600 and b.frame > 600:
            break
    t2 = time.time()
    print(f'\n=== 效率 ===')
    print(f'  模拟 {b.frame} 帧（{b.frame/30:.1f} 秒游戏时间）耗时 {t2-t1:.3f}s'
          f'  ⇒ **{(b.frame/30)/(t2-t1):.1f}× 实时**')
    print(f'  单帧平均 {((t2-t1)/max(1,b.frame))*1000:.3f} ms')

    # ---- 与标定表对照 ----
    ev = extract_events(b.frames)
    print(f'\n=== 模拟器事件（共 {len(ev)} 条）与标定表对照 ===')
    by_t = {}
    for e in ev:
        by_t.setdefault(e['frame'], []).append(e)
    print('  —— 部署与费用 ——')
    for row in results:
        f, char, rc, direc, ok, cost = row
        mark = 'OK' if ok else '★失败'
        print(f'    帧 {f:>4}: 部署 {char}@{rc} 朝{direc} {mark} 费用={cost:.1f}')
    print('  —— 费用（标定该秒初始费用 vs 模拟器）——')
    for sec, want in sorted(CALIB_COST.items()):
        f = sec * 30
        near = [x for x in b.frames if x['f'] == f]
        got = near[0]['cost'] if near else None
        diff = '' if (got is None) else f'{got-want:+.1f}'
        mark = 'OK' if (got is not None and abs(got - want) < 0.6) else '★差异'
        print(f'    {sec:>2}s (帧{f:>4}): 标定={want:>4}  模拟={got}  Δ={diff} {mark}')

    print('\n  —— 标定的动画层事件（模拟器对应事件）——')
    for f, unit, desc in CALIB_ANIM:
        near = [e for e in ev if abs(e['frame'] - f) <= 6 and e['type'] in
                ('spawn', 'damage', 'damage_first', 'cost_up', 'cost_spend', 'deploy')]
        s = '; '.join(f"{e['type']}@{e['frame']}" for e in near[:2]) or '（无同类事件）'
        print(f'    帧 {f:>4} [{unit}] {desc}  ⇒ 模拟器近邻事件: {s}')

    out = os.path.join(r'C:\Users\23922\Documents\ds_harness\ak\.tmp', 'replay_11calib.json')
    json.dump({'results': results, 'events': ev[:400]}, open(out, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print(f'\n  明细已写 {out}')


if __name__ == '__main__':
    main()
