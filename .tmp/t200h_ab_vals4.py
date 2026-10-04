# -*- coding: utf-8 -*-
"""T-200h：全库找带 `_preDelay` 的能力组件，打印其 GameObject 名 + 各字段。

只读 E 盘。
"""
from __future__ import annotations

import glob
import os
import sys

sys.path.insert(0, r'C:\Users\23922\Documents\ds_harness\ak\scripts')
from UnityPy.enums.BundleFile import CompressionFlags          # noqa: E402
from UnityPy.helpers import CompressionHelper                   # noqa: E402
from ak_lz4ak import decompress_lz4ak                           # noqa: E402

CompressionHelper.DECOMPRESSION_MAP[CompressionFlags.LZHAM] = decompress_lz4ak

import UnityPy                                                  # noqa: E402

sys.stdout.reconfigure(encoding='utf-8')

FIELDS = ('_preDelay', '_timeMode', '_maxAnimScale', '_animKey', '_waitForAttackEvent',
          '_cooldown', '_resetCdStrategy', '_preDelayFactor', '_atkScale', '_attackType',
          '_selectTargetTiming')


def go_name_map(env):
    """path_id(GameObject) -> m_Name；path_id(MonoBehaviour) 通过 m_GameObject 反查。"""
    m = {}
    for obj in env.objects:
        if obj.type.name == 'GameObject':
            try:
                m[obj.path_id] = obj.read().m_Name
            except Exception:                                    # noqa: BLE001
                pass
    return m


def names_all(env):
    out = {}
    for obj in env.objects:
        if obj.type.name != 'MonoBehaviour':
            continue
        try:
            tt = obj.read_typetree()
        except Exception:                                        # noqa: BLE001
            continue
        if isinstance(tt, dict) and '_preDelay' in tt:
            g = tt.get('m_GameObject') or {}
            gid = g.get('m_PathID') if isinstance(g, dict) else None
            out[gid] = tt
    return out


def run(path, tag_filter=None):
    env = UnityPy.load(path)
    gmap = go_name_map(env)
    hits = names_all(env)
    if not hits:
        return
    print(f'\n===== {os.path.basename(path)}  含 _preDelay 的 MB: {len(hits)} =====')
    for gid, tt in hits.items():
        gname = gmap.get(gid, '?')
        if tag_filter and tag_filter not in str(gname):
            continue
        print(f'  GO={gname!r}')
        for k in FIELDS:
            if k in tt:
                print(f'      {k} = {tt[k]}')


if __name__ == '__main__':
    enm = r'E:\__file\ak_kb\client_res\enm_pfb'
    for fn in ('enm_pfb_0.ab', 'enm_pfb_base_0.ab'):
        run(os.path.join(enm, fn), tag_filter='gopro')
    cp = r'E:\__file\ak_kb\client_res\charpack'
    for fn in ('char_123_fang.ab', 'char_283_midn.ab'):
        run(os.path.join(cp, fn))
