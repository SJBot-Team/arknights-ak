# -*- coding: utf-8 -*-
"""probe_first_dragon.py — 「首条弦惊最早何时能落地」的费用账本 + 模拟器搜索

## 背景（§7.53 的悬案）
作者轴表记 29.0s 落首龙，但模拟器在该时刻读到 `need=18, have=9` ⇒ 按作者记录**根本部署不了**。
本轮把这件事量化：
  1. **纯费用账本**：cap=20、初始 10、+1/s；令 10 费、蕾缪安 20 费、弦惊（令模组后）18 费。
     设令在 t_L 部署、蕾缪安在 t_M 部署，则弦惊最早可在
     `t_d = 费用首次回到 18 的时刻` 部署 ⇒ 可解析算出。
  2. **模拟器实跑**：把"令/蕾缪安/弦惊"三条操作的**时刻参数化**（格子沿用作者轴表），
     对若干候选组合跑 Battle，记录**首个 ok=True 的弦惊部署帧**与漏怪情况。

⇒ 得到"最早可行落龙时刻"，与作者的 29.0s 对照，判定作者记录是**按键意图时刻**还是**可行时刻**。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim import scenario_h124 as S            # noqa: E402
from ak_sim.axis import parse_cyberplastic        # noqa: E402
from ak_sim.engine import Battle                  # noqa: E402

FPS = 30
DRAGON = 'token_10020_ling_soul3'


def ledger(cap=20.0, init=10.0, rate=1.0, cost_ling=10.0, cost_lem=20.0, cost_dragon=18.0):
    """纯费用账本：给定令/蕾缪安的部署时刻，算弦惊最早可部署时刻。

    费用曲线：cost(t) = min(cap, init + rate*t) - Σ(已部署的费用)，且费用不能为负（部署需付得起）。
    """
    def earliest_dragon(t_ling, t_lem=None):
        cur = init
        last = 0.0
        spends = [(t_ling, cost_ling)]
        if t_lem is not None:
            spends.append((t_lem, cost_lem))
        spends.sort()
        for t_s, c in spends:
            cur = min(cap, cur + rate * (t_s - last))
            if cur < c:                       # 付不起 ⇒ 顺延到付得起
                t_s = last + (c - cur) / rate
                cur = min(cap, cur + rate * (t_s - last))
            cur -= c
            last = t_s
            deployed_at = t_s
        # 攒到弦惊的费用
        need = cost_dragon - cur
        if need <= 0:
            return max(last, t_ling if t_lem is None else max(t_ling, t_lem))
        return last + need / rate

    return earliest_dragon


def main():
    ax = parse_cyberplastic(S.XLSM)
    # 取作者轴表里"令 / 蕾缪安 / 弦惊"三条**部署**操作的模板（格子沿用作者的 coord）
    # 注意：o.unit 是中文名；坐标字段是 coord；时刻字段是 abs_seconds（不是 frame/row/col）
    tmpl = {}
    for o in ax.ops:
        d = o.to_dict()
        if d.get('op') != 'deploy':
            continue
        nm = o.unit
        if nm == '弦惊' and 'dragon' not in tmpl:
            tmpl['dragon'] = d
        elif nm in ('令', '蕾缪安') and nm not in tmpl:
            tmpl[nm] = d
    print('作者轴表中的模板操作：')
    for k, v in tmpl.items():
        print(f'   {k:<8} abs_seconds={v.get("abs_seconds")} coord={v.get("coord")} dir={v.get("dir")} cost={v.get("cost")}')

    ed = ledger()
    print('\n=== 纯费用账本（cap=20, init=10, +1/s；令10 蕾20 弦18）===')
    print('  令部署时刻  蕾缪安时刻   → 弦惊最早可部署')
    for t_ling in (0.0, 5.0, 10.0, 11.0, 15.0):
        for t_lem in (None, t_ling + 20.0):
            t_d = ed(t_ling, t_lem)
            print(f'   {t_ling:5.1f}s      {("—" if t_lem is None else f"{t_lem:5.1f}s")}      → {t_d:6.1f}s')

    # 模拟器实跑：只放三条操作（令/蕾缪安/弦惊），时刻参数化
    def build_ops(t_ling, t_lem, t_dragon):
        ops = []
        for key, t in (('令', t_ling), ('蕾缪安', t_lem), ('dragon', t_dragon)):
            if key not in tmpl or t is None:
                continue
            d = dict(tmpl[key])
            d['frame'] = int(round(t * FPS))
            d['char'] = S.NAME_MAP.get(d['unit'], d['unit'])
            for k, v in S.UNIT_CONFIG.get(d['char'], {}).items():
                d.setdefault(k, v)
            ops.append(d)
        ops.sort(key=lambda x: x['frame'])
        return ops

    print('\n=== 模拟器实跑（只放 令/蕾缪安/弦惊 三条，格子沿用作者）===')
    print('  令@   蕾@   弦惊@   → 实际落地/结果')
    for (t_ling, t_lem, t_dr) in ((0.0, None, 18.0), (10.0, None, 28.0), (11.0, None, 29.0),
                                  (11.0, 20.0, 38.0), (11.0, 20.0, 29.0)):
        ops = build_ops(t_ling, t_lem, t_dr)
        b = Battle(S.LEVEL, seed=0, record=False)
        fired = b.run_axis(ops, name_map=S.NAME_MAP, coord_transform=S.COORD_TRANSFORM,
                           max_frames=30 * 120, continue_after_fail=False,
                           retry_on_cost=True, retry_on_sp=False,
                           schedule=[o['frame'] for o in ops])
        lands = [round(x['frame'] / FPS, 1) for x in fired
                 if x.get('op') == 'deploy' and x.get('unit') == DRAGON and x.get('ok')]
        fails = [round(x['frame'] / FPS, 1) for x in fired
                 if x.get('op') == 'deploy' and x.get('unit') == DRAGON and not x.get('ok')]
        print(f'  {t_ling:4.1f}  {("—" if t_lem is None else f"{t_lem:4.1f}")}  {t_dr:5.1f}   '
              f'→ 落地{lands or "无"} 失败尝试{fails or "无"}  结果={b.result} 生命{b.life} '
              f'帧{b.frame}({b.frame/FPS:.0f}s)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
