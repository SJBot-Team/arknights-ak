# -*- coding: utf-8 -*-
"""T-200h：把目标 prefab 的**整个 GameObject 子树**摊开，找挂 `_preDelay` 的能力组件。

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

FIELDS = ['_preDelay', '_timeMode', '_maxAnimScale', '_animKey', '_endAnimKey',
          '_waitForAttackEvent', '_cooldown', '_resetCdStrategy', '_preDelayFactor',
          '_recalculatePlaybackSpeed', '_selectTargetTiming', '_atkScale', '_attackType']


def dump(prefab_file, root_names):
    env = UnityPy.load(prefab_file)
    go_by_id = {}
    tr_by_id = {}
    for obj in env.objects:
        try:
            if obj.type.name == 'GameObject':
                d = obj.read()
                go_by_id[obj.path_id] = d
            elif obj.type.name == 'Transform':
                tr_by_id[obj.path_id] = obj.read()
        except Exception:                                        # noqa: BLE001
            continue
    # 建父子关系
    children = {}
    parent = {}
    for tid, tr in tr_by_id.items():
        try:
            gid = tr.m_GameObject.path_id
        except Exception:                                        # noqa: BLE001
            continue
        p = getattr(tr, 'm_Father', None)
        if p is not None and getattr(p, 'path_id', 0):
            children.setdefault(p.path_id, []).append(tid)
            parent[tid] = p.path_id
    def walk(tid, depth):
        out = [(tid, depth)]
        for c in children.get(tid, []):
            out += walk(c, depth + 1)
        return out

    print(f'\n===== {os.path.basename(prefab_file)} roots={sorted(root_names)} =====')
    for obj in env.objects:
        if obj.type.name != 'GameObject':
            continue
        d = go_by_id.get(obj.path_id)
        if d is None or d.m_Name not in root_names:
            continue
        # 找它的 Transform
        tr_id = None
        for c in (getattr(d, 'm_Component', None) or []):
            try:
                cc = c.component.read()
            except Exception:                                    # noqa: BLE001
                continue
            if type(cc).__name__ == 'Transform':
                tr_id = c.component.path_id
        print(f'\n--- root {d.m_Name}  (transform {tr_id})')
        if tr_id is None:
            continue
        for tid, depth in walk(tr_id, 0):
            tr = tr_by_id.get(tid)
            gid = getattr(getattr(tr, 'm_GameObject', None), 'path_id', None)
            g = go_by_id.get(gid)
            if g is None:
                continue
            hits = []
            for c in (getattr(g, 'm_Component', None) or []):
                try:
                    cc = c.component.read()
                except Exception:                                # noqa: BLE001
                    continue
                if type(cc).__name__ != 'MonoBehaviour':
                    continue
                try:
                    tt = cc.read_typetree()
                except Exception:                                # noqa: BLE001
                    continue
                if not isinstance(tt, dict):
                    continue
                hit = {k: tt.get(k) for k in FIELDS if k in tt}
                if hit:
                    hits.append((tt.get('m_Name') or '', hit))
            if hits:
                print(f'  {"  "*depth}GO {g.m_Name!r} (depth {depth})')
                for nm, hit in hits:
                    print(f'  {"  "*depth}   MB {nm!r}: {hit}')


if __name__ == '__main__':
    enm = r'E:\__file\ak_kb\client_res\enm_pfb'
    for fn in ('enm_pfb_0.ab', 'enm_pfb_base_0.ab'):
        p = os.path.join(enm, fn)
        if os.path.exists(p):
            dump(p, {'enemy_1000_gopro', 'enemy_1000_gopro_2'})
    cp = r'E:\__file\ak_kb\client_res\charpack'
    for fn in ('char_123_fang.ab', 'char_283_midn.ab'):
        p = os.path.join(cp, fn)
        if os.path.exists(p):
            dump(p, {'char_123_fang', 'char_283_midn'})
