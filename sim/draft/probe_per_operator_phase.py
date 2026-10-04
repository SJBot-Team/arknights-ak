# -*- coding: utf-8 -*-
"""probe_per_operator_phase.py — ★实测"不同干员的阻挡扫描相位不同"。

## 依据（用户 2026-09-15）
「阻挡扫描帧与**干员部署帧**高度相关，且**不同干员存在差异**」
—— `Character.m_findBlockeeTicker`（`PeriodicTicker`，偏移 0x380）为**每角色**计时器。

## 本脚本
跑 1-1 标定对局，记录：
①每位干员的 `spawn_frame`（=部署帧）与其**扫描相位** `(spawn_frame + phase) % 3`；
②该干员**实际发生阻挡判定**的帧序列（通过在 `_block_ticker_fires` 上挂钩子采集）；
③验证"实际扫描帧 ≡ 相位 (mod 3)"且**不同干员相位不同**。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

import ak_sim.engine as E                        # noqa: E402
from sweep_hit_volume import run                 # noqa: E402

SCANS: dict[str, list[int]] = {}
_orig = E.Battle._block_ticker_fires


def patched(self, o):
    ok = _orig(self, o)
    if ok:
        SCANS.setdefault(getattr(o, 'name', '?'), []).append(self.frame)
    return ok


E.Battle._block_ticker_fires = patched

b = run({})
print('=== 每位干员的部署帧 / 扫描相位 / 实际扫描帧 ===')
for u in b.units.values():
    if u.side != 'ALLY':
        continue
    sf = getattr(u, 'spawn_frame', None)
    ph = (int(sf or 0)) % 3
    frames = SCANS.get(u.name, [])
    uniq = sorted(set(frames))
    show = uniq[:8]
    bad = [f for f in uniq if f % 3 != ph]
    print(f'  {u.name:<5} 部署帧={sf:<4} 相位={ph}  实际扫描 {len(uniq)} 帧，前 8 = {show}')
    print(f'        相位一致性：{"✅ 全部 ≡ %d (mod 3)" % ph if not bad else "❌ 有 %d 帧不符" % len(bad)}')

print('\n=== 阻挡事件 ===')
for l in b.logs:
    if l.kind in ('block', 'block_offset'):
        print(f'  帧 {l.frame:>4} {l.kind:<12} {l.detail}')
