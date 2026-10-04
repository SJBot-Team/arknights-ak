# -*- coding: utf-8 -*-
"""probe_cost_diff.py — 定位"1-1 标定复刻"中费用恒定偏少 1 的来源

## 现象
- 0s：Δ=0；**3~13s：Δ=−1**；**14~18s：Δ=−2**（每部署一次少 1）
- 帧 10 部署芬后，模拟器费用 = **1.0**；按 `10 + 0.33 − 8 = 2.33` 推算差了 1.33

## 本脚本检查
1. 芬（char_123_fang）/ 月见夜（char_283_midn）在**满潜/默认潜能**下的实际部署费用；
2. 模拟器 `deploy()` 的扣费逻辑（读源码片段）；
3. 逐帧打印 0~20 帧的费用，看**扣费发生在部署帧之前还是之后**；
4. 打印"仅增长不部署"对照曲线，确认 +1/s 的相位。
"""
from __future__ import annotations

import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim import data as D            # noqa: E402
from ak_sim.engine import Battle        # noqa: E402
from ak_sim.scenario import Scenario    # noqa: E402

STAGE = '1-1'
FANG, MIDN = 'char_123_fang', 'char_283_midn'


def op_cost(char_id, potential=0):
    """从 data 层取干员费用（指定潜能）。"""
    try:
        spec = D.get_operator(char_id, elite=2, level=90, potential=potential, trust=200)
    except Exception as e:
        return f'<取失败 {e}>'
    return spec.get('cost')


def main():
    print('=== 一、干员费用（不同潜能）===')
    for cid in (FANG, MIDN):
        for pot in (0, 1, 2, 3, 4, 5, 6):
            c = op_cost(cid, pot)
            print(f'  {cid}  潜能{pot}: cost={c}')
        print()

    print('=== 二、模拟器 deploy 的扣费逻辑（源码片段）===')
    src = inspect.getsource(Battle.deploy)
    for i, line in enumerate(src.splitlines()):
        if 'cost' in line:
            print(f'  {line.strip()}')

    print('\n=== 三、逐帧费用（前 40 帧，不部署）===')
    sc = Scenario(STAGE)
    b = Battle(sc.stage_code, seed=0, record=True, record_every=1, max_frames=200)
    print('  帧: 费用')
    row = []
    for f in range(40):
        b.tick()
        row.append(f'{b.frame}:{b.cost:g}')
    print('  ' + '  '.join(row))

    print('\n=== 四、帧 10 部署芬：逐帧费用（含部署前后）===')
    b2 = Battle(sc.stage_code, seed=0, record=True, record_every=1, max_frames=200)
    for f in range(14):
        b2.tick()
        note = ''
        if b2.frame == 10:
            u = b2.deploy(FANG, 3, 5, direction='左', elite=2, level=90,
                          potential=6, trust=200, skill_index=0, skill_level=7)
            note = f'  ← 部署芬 {"成功" if u else "失败"}'
        print(f'  帧 {b2.frame:>3}: 费用 = {b2.cost:>6.2f}{note}')

    print('\n=== 五、标定表对照（该秒初始费用）===')
    print('  标定: 0s=10, 3s=5  ⇒ 部署芬(8费)后 3 秒应为 5')
    print('  若初始 10、+1/s、扣 8 ⇒ 帧10(0.33s) 部署后 = 10+0.33-8 = 2.33')
    print('  而模拟器实测 = 1.0 ⇒ 差 1.33')


if __name__ == '__main__':
    main()
