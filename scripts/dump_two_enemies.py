# -*- coding: utf-8 -*-
"""dump_two_enemies.py — ★完整导出 1-1 两种敌人的组件树与全部碰撞体（找两敌的真正差别）。

背景（第114轮）：两敌在索敌上**要求相反的修正** ——
`猎狗pro` 恰在"中心进入范围格"时被索敌（现规则正确），
`猎狗` 需在"距范围区域约 0.8 格"处即被索敌。
已排除：受击半径（皆 0.1）、移速（皆 0.95）、阻挡半径（皆 0.7071）、范围表（2 格）。
⇒ 本轮把两敌的 prefab **完整摊开**：全部组件、全部 Collider（含 Capsule/Box）、偏移、缩放、子对象。
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

WANT = {'enemy_1000_gopro', 'enemy_1000_gopro_2', 'enemy_1000_gopro_3'}
PATH = r'E:\__file\ak_kb\client_res\enm_pfb\enm_pfb_0.ab'

env = UnityPy.load(PATH)
gos = {}
for obj in env.objects:
    if obj.type.name != 'GameObject':
        continue
    try:
        d = obj.read()
    except Exception:                                            # noqa: BLE001
        continue
    if d.m_Name in WANT:
        comps = []
        for c in (getattr(d, 'm_Component', None) or []):
            try:
                cc = c.component.read()
            except Exception:                                    # noqa: BLE001
                continue
            tn = type(cc).__name__
            info = {'type': tn}
            for f in ('m_Radius', 'm_Size', 'm_Offset', 'm_Center', 'm_Enabled',
                      'm_LocalScale', 'm_LocalPosition', 'm_LocalRotation',
                      'm_IsTrigger', 'm_UsedByEffector', 'm_UsedByComposite',
                      'm_Script', 'm_Name'):
                if hasattr(cc, f):
                    v = getattr(cc, f)
                    info[f] = str(v)[:60]
            comps.append(info)
        gos[d.m_Name] = comps

for nm in sorted(gos):
    print(f'=== {nm} （{len(gos[nm])} 个组件）===')
    for c in gos[nm]:
        keys = {k: v for k, v in c.items() if k != 'type' and v not in ('None',)}
        print(f'   {c["type"]:<24} {keys}')
