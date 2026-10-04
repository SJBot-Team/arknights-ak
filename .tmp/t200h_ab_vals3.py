# -*- coding: utf-8 -*-
"""T-200h：直接按 GameObject 名找能力组件并打印全字段（不依赖 Transform 树）。

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

WANT_FIELDS = ('_preDelay', '_timeMode', '_maxAnimScale', '_animKey', '_waitForAttackEvent',
               '_cooldown', '_resetCdStrategy', '_atkScale', '_attackType', '_preDelayFactor')


def dump(path, go_names, all_fields=False):
    env = UnityPy.load(path)
    print(f'\n===== {os.path.basename(path)} =====')
    for obj in env.objects:
        if obj.type.name != 'GameObject':
            continue
        try:
            d = obj.read()
        except Exception:                                        # noqa: BLE001
            continue
        if d.m_Name not in go_names:
            continue
        for c in (getattr(d, 'm_Component', None) or []):
            try:
                cc = c.component.read()
            except Exception:                                    # noqa: BLE001
                continue
            tn = type(cc).__name__
            if tn != 'MonoBehaviour':
                continue
            try:
                tt = cc.read_typetree()
            except Exception:                                    # noqa: BLE001
                continue
            if not isinstance(tt, dict):
                continue
            hit = {k: tt.get(k) for k in WANT_FIELDS if k in tt}
            if hit or all_fields:
                print(f'  GO={d.m_Name!r} MB={tt.get("m_Name")!r}')
                if all_fields and not hit:
                    print(f'      字段名: {list(tt.keys())}')
                for k, v in hit.items():
                    print(f'      {k} = {v}')


if __name__ == '__main__':
    enm = r'E:\__file\ak_kb\client_res\enm_pfb'
    dump(os.path.join(enm, 'enm_pfb_0.ab'), {'enemy_1000_gopro', 'enemy_1000_gopro_2'})
    dump(os.path.join(enm, 'enm_pfb_base_0.ab'), {'enemy_1000_gopro', 'enemy_1000_gopro_2'})
    cp = r'E:\__file\ak_kb\client_res\charpack'
    dump(os.path.join(cp, 'char_123_fang.ab'), {'Attack', 'char_123_fang'}, all_fields=True)
    dump(os.path.join(cp, 'char_283_midn.ab'), {'Attack', 'char_283_midn'}, all_fields=True)
