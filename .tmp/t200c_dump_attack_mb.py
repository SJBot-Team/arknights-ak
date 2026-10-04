# -*- coding: utf-8 -*-
r"""t200c_dump_attack_mb.py — 从干员 charpack 里取出 `Attack` 组件的 MonoBehaviour 原始数据，
并列出其中的候选 float（找 `_preDelay` 等时间量）。T-200c / 04/71 缺口①

用法：
    python t200c_dump_attack_mb.py char_123_fang [--hex 96]
"""
from __future__ import annotations

import argparse
import os
import struct
import sys

sys.stdout.reconfigure(encoding='utf-8')

CLIENT_RES = r'E:\__file\ak_kb\client_res'
TOOLS = r'C:\Users\23922\Documents\ds_harness\ak\code\tools'


def register():
    import UnityPy
    from UnityPy.enums import CompressionFlags
    from UnityPy.helpers import CompressionHelper as C
    if TOOLS not in sys.path:
        sys.path.insert(0, TOOLS)
    from ak_lz4ak import decompress_lz4ak
    C.DECOMPRESSION_MAP[CompressionFlags.LZHAM] = decompress_lz4ak
    return UnityPy


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('unit')
    ap.add_argument('--hex', type=int, default=0)
    ap.add_argument('--ab', default=None, help='直接指定 ab 文件名（默认按 unit 试 charpack/<unit>.ab）')
    a = ap.parse_args()
    UnityPy = register()
    ab = a.ab or os.path.join('charpack', f'{a.unit}.ab')
    p = ab if os.path.isabs(ab) else os.path.join(CLIENT_RES, ab)
    env = UnityPy.load(p)

    gos, mbs = {}, []
    for obj in env.objects:
        t = obj.type.name
        if t == 'GameObject':
            d = obj.read()
            gos[obj.path_id] = getattr(d, 'm_Name', '')
        elif t == 'MonoBehaviour':
            d = obj.read()
            raw = getattr(d, 'm_RawData', None)
            if raw is None:
                try:
                    raw = obj.get_raw_data()
                except Exception:
                    raw = b''
            mbs.append((obj, d, raw))

    print(f'{os.path.basename(p)}: GameObject {len(gos)} 个, MonoBehaviour {len(mbs)} 个')
    print('GameObject 名:', ', '.join(sorted(n for n in gos.values() if n)))

    for obj, d, raw in mbs:
        # 组件的宿主 GameObject 名（通过 m_GameObject 引用）
        host = ''
        try:
            go = getattr(d, 'm_GameObject', None)
            if go is not None:
                host = gos.get(getattr(go, 'path_id', None), '')
        except Exception:
            pass
        script = ''
        try:
            mono = getattr(d, 'm_Script', None)
            script = getattr(mono, 'm_Name', '') if mono is not None else ''
        except Exception:
            pass
        print(f'\n--- MonoBehaviour @{obj.path_id}  host={host!r}  script={script!r}  raw={len(raw)} B ---')
        if a.hex:
            print('  hex:', raw[:a.hex].hex(' '))
        # 候选 float（0.001 ~ 100，排除 NaN/Inf）
        cands = []
        for i in range(0, len(raw) - 3, 4):
            (f,) = struct.unpack_from('<f', raw, i)
            if 0.001 <= f <= 100.0 and abs(f) > 0:
                cands.append((i, round(f, 6)))
        if cands:
            print('  候选 float（偏移: 值）:')
            for i, f in cands[:40]:
                print(f'    +0x{i:03x}: {f}')
        else:
            print('  （无候选 float）')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
