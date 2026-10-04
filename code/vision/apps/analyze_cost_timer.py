# -*- coding: utf-8 -*-
"""analyze_cost_timer.py — 从录像扫描结果重建"PRTS+ 口径计时器"，并量化封顶边界的误差

## 依据（用户 2026-09-14 的澄清，§7.138）
PRTS+ 的计时：**费用条每满一次记 30 帧（1 秒）**；封顶后条停止跳动 ⇒ **它的计时器也停止**；
由于它**不能识别"条已满"**，费用重新流动时会**误判满的次数多一次或少一次** ⇒ **1 秒误差**。

## 本脚本怎么算
1. 从扫描结果取**费用数字发生变化的帧**（每次 +1 = 该计时器记 1 秒）；
2. 由间隔判断速度倍率与封顶：
   - 正常段（本例 2X）：费用 +1 间隔应 ≈ **15 视频帧**；
   - **封顶段**：费用长期不变 ⇒ 间隔远大于 15；
3. 于是可算出两种口径的时间：
   - **游戏时间**（逻辑秒）= 视频帧 / 15（2X 下）；
   - **PRTS+ 计时器读数** = (费用变化的次数) + 当前相位/30；
4. 二者之差即"该计时器与游戏时间的偏差"，并逐段给出封顶造成的落差与**边界 ±1 次**的影响。
"""
from __future__ import annotations

import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

TMP = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(TMP, 'video_scan_明日方舟(128).json')
    d = json.load(open(path, encoding='utf-8'))
    rows = d['rows']
    fps = d['fps']
    chg = [(f, a, b) for f, a, b in d['cost_changes']]
    print(f'视频 {os.path.basename(d["file"])}：扫描 {len(rows)} 帧，费用变化 {len(chg)} 次')

    # 相邻 +1 的帧间隔
    inc = [(chg[i][0], chg[i][0] - chg[i - 1][0]) for i in range(1, len(chg))
           if chg[i][2] == chg[i][1] + 1]
    gaps = [g for _f, g in inc]
    if not gaps:
        print('没有连续 +1 样本'); return 1
    from collections import Counter
    cnt = Counter(gaps)
    print(f'\n=== 费用 +1 的帧间隔分布（前 8）===')
    for g, c in cnt.most_common(8):
        print(f'   {g:>4} 视频帧  × {c} 次')
    normal = cnt.most_common(1)[0][0]
    print(f'   ⇒ 众数间隔 = {normal} 视频帧 ⇒ 判定倍率为 **{30/normal:.1f}X**'
          f'（1 逻辑秒 = {normal} 视频帧）')

    # 封顶段：间隔明显大于众数
    print(f'\n=== 疑似封顶段（间隔 > {normal*2} 视频帧）===')
    stall = [(f, g) for f, g in inc if g > normal * 2]
    for f, g in stall[:20]:
        print(f'   帧{f:>6} 距上次 +1 过了 {g:>4} 视频帧（≈{g/normal:6.1f} 逻辑秒，其中约 '
              f'{g/normal-1:6.1f} 秒是封顶）')

    # 边界间隔：封顶之后（或之前）出现的"偏短/偏长"间隔 ⇒ ±1 次歧义的直接证据
    print('\n=== 边界间隔（封顶相邻的 +1 间隔，检验 ±1 次歧义）===')
    bnd = []
    for i in range(1, len(inc)):
        f, g = inc[i]
        _pf, pg = inc[i - 1]
        if pg > normal * 2 or g > normal * 2:      # 与前一次或本身是封顶跨越
            bnd.append((f, g, pg))
    for f, g, pg in bnd[:20]:
        note = ''
        if g < normal - 1:
            note = f'★ 偏短 {normal-g} 视频帧 ⇒ 相当于"少记了一次满"（约 −1 秒）'
        elif g > normal + 1:
            note = f'★ 偏长 {g-normal} 视频帧 ⇒ 相当于"多算/漏算"'
        print(f'   帧{f:>6} 间隔 {g:>4}（上一次 {pg:>4}）{note}')

    # 两种口径的时间对照（以首个非零费用为原点）
    base_f, base_c = chg[0][0], chg[0][2]
    print('\n=== 口径对照（游戏逻辑秒 vs PRTS+ 计时器读数）===')
    print('   帧号     游戏秒   计时器秒   差')
    n = 0
    for f, a, b in chg:
        if b != a + 1:
            continue
        game = (f - base_f) / normal
        timer = (b - base_c)
        diff = timer - game
        if n % 40 == 0 or abs(diff) > 2:
            print(f'   {f:>6}  {game:8.2f}  {timer:9.0f}  {diff:+7.2f}')
        n += 1
    print('\n说明：计时器读数 = 费用每 +1 记 1 秒（封顶期间不记）；'
          '差值随每次封顶下跳（封顶时长），边界处的 ±1 次判定再叠加 ±1 秒。')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
