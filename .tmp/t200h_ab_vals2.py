# -*- coding: utf-8 -*-
"""T-200h：精确定位 1-1 三只敌人（gopro / gopro_2）+ 芬 / 月见夜 的**普攻能力** prefab 真值。

输出每个普攻能力组件的 `_preDelay` / `_timeMode` / `_maxAnimScale` / `_animKey` /
`_waitForAttackEvent` / `_cooldown` 等。
只读 E 盘。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, r'C:\Users\23922\Documents\ds_harness\ak\scripts')
from UnityPy.enums.BundleFile import CompressionFlags          # noqa: E402
from UnityPy.helpers import CompressionHelper                   # noqa: E402
from ak_lz4ak import decompress_lz4ak                           # noqa: E402

CompressionHelper.DECOMPRESSION_MAP[CompressionFlags.LZHAM] = decompress_lz4ak

import UnityPy                                                  # noqa: E402

sys.stdout.reconfigure(encoding='utf-8')

FIELDS = ['m_Name', '_preDelay', '_timeMode', '_maxAnimScale', '_animKey', '_endAnimKey',
          '_waitForAttackEvent', '_cooldown', '_resetCdStrategy', '_preDelayFactor',
          '_recalculatePlaybackSpeed', '_selectTargetTiming', '_atkScale',
          '_minPostDelay', '_attackType']


def read_all(path, want_go):
    env = UnityPy.load(path)
    gos = {}
    for obj in env.objects:
        if obj.type.name != 'GameObject':
            continue
        try:
            d = obj.read()
        except Exception:                                        # noqa: BLE001
            continue
        gos[obj.path_id] = d
    # 直接挂在这些 GO 上的 MonoBehaviour
    out = []
    for oid, d in gos.items():
        if d.m_Name not in want_go:
            continue
        for c in (getattr(d, 'm_Component', None) or []):
            try:
                cc = c.component.read()
            except Exception:                                    # noqa: BLE001
                continue
            if type(cc).__name__ != 'MonoBehaviour':
                continue
            try:
                tt = cc.read_typetree()
            except Exception:                                    # noqa: BLE001
                continue
            if not isinstance(tt, dict):
                continue
            hit = {k: tt.get(k) for k in FIELDS if k in tt}
            if hit:
                out.append((d.m_Name, tt.get('m_Name') or '', hit))
    return out


def probe(path, want_go):
    print(f'\n===== {os.path.basename(path)} want={sorted(want_go)} =====')
    rows = read_all(path, want_go)
    if not rows:
        print('  （无命中：目标 GO 可能只作为父节点，能力挂子对象）')
    for gname, mbname, hit in rows:
        if any(k in hit for k in ('_preDelay', '_maxAnimScale', '_animKey')):
            print(f'  GO={gname!r} MB={mbname!r}')
            for k in FIELDS:
                if k in hit:
                    print(f'      {k} = {hit[k]}')
    return rows


if __name__ == '__main__':
    enm = r'E:\__file\ak_kb\client_res\enm_pfb'
    for fn in ('enm_pfb_0.ab', 'enm_pfb_base_0.ab'):
        p = os.path.join(enm, fn)
        if os.path.exists(p):
            probe(p, {'enemy_1000_gopro', 'enemy_1000_gopro_2'})
    cp = r'E:\__file\ak_kb\client_res\charpack'
    for fn in ('char_123_fang.ab', 'char_283_midn.ab'):
        p = os.path.join(cp, fn)
        if os.path.exists(p):
            probe(p, {'char_123_fang', 'char_283_midn'})
