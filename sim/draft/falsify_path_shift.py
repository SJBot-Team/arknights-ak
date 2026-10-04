# -*- coding: utf-8 -*-
"""falsify_path_shift.py — ★证伪实验：敌人路径整体前移能否同时满足两个观测。

## 两个约束（依 1-1 标定）
- **索敌/命中**：`芬→猎狗` 标定 **432** ⇒ 反推索敌 ≈ 432 − 18(前摇) = **414**；模拟现为 **439/457** ⇒ 需**提前 ~25 帧**；
- **阻挡**：`芬 阻挡 猎狗` 标定 **443**；模拟现为 **446** ⇒ 仅差 **+3 帧**。

## 论证
路径前移 Δ 格 ⇒ 进入范围与进入阻挡半径**一起**提前 ⇒ 二者偏差**同向变化**，
不可能只把前者提前 25 帧而后者几乎不动 ⇒ **可事先预期证伪**；本脚本给出实证。

## 做法（不改引擎，用猴补丁把敌人出生位置沿路径前移）
`route_start_advance`（格）：出生后把敌人位置沿其路径方向前移该距离。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

import ak_sim.engine as E                        # noqa: E402
import ak_sim.fp as fp                           # noqa: E402
from sweep_hit_volume import run                 # noqa: E402

_orig_spawn = E.Battle._spawn_enemy
ADV = [0.0]


def patched(self, a):
    _orig_spawn(self, a)
    d = ADV[0]
    if not d:
        return
    u = max(self.units.values(), key=lambda z: z.uid)
    try:
        import math as _m
        x, y = fp.to_float(u.pos[0]), fp.to_float(u.pos[1])
        # 取该敌人的路径终点（不同字段名都试一遍），据此沿路径方向前移 d 格
        tgt = None
        for attr in ('end', 'end_point', 'target', 'nodes'):
            v = getattr(u.route, attr, None)
            if v is None:
                continue
            if attr == 'nodes' and isinstance(v, (list, tuple)) and v:
                v = v[-1]
            if isinstance(v, (tuple, list)) and len(v) == 2:
                tgt = v
                break
        if tgt is None:
            return
        tr, tc = tgt
        tx, ty = tc + 0.5, tr + 0.5
        vx, vy = tx - x, ty - y
        n = _m.hypot(vx, vy) or 1.0
        u.pos = (fp.from_float(x + vx / n * d), fp.from_float(y + vy / n * d))
    except Exception:                                              # noqa: BLE001
        return


E.Battle._spawn_enemy = patched

print(f'{"路径前移(格)":>10} {"芬→猎狗命中":>12} {"(标定432)":>10} {"阻挡帧":>10} {"(标定443)":>10} '
      f'{"伤害平均":>8} {"最大":>5}')
from sweep_hit_volume import score                # noqa: E402
for d in (0.0, 0.2, 0.4, 0.6, 0.8, 1.0, 1.2):
    ADV[0] = d
    b = run({})
    hits = [l.frame for l in b.logs
            if l.kind == 'hit' and l.detail.get('src') == '芬' and l.detail.get('tgt') == '猎狗']
    blk = [l.frame for l in b.logs if l.kind == 'block' and l.detail.get('enemy') == '猎狗']
    a, h, m, _ = score(b)
    h0 = hits[0] if hits else None
    b0 = blk[0] if blk else None
    print(f'{d:>10} {str(h0):>12} {(h0-432) if h0 else None:>10} {str(b0):>10} '
          f'{(b0-443) if b0 else None:>10} {a:>8.2f} {m:>5}')
print('\n目标：命中偏差 ≈ −25（提前到 432）且阻挡偏差 ≈ 0~+3；'
      '若二者同向变化 ⇒ 路径假说被证伪')
