# -*- coding: utf-8 -*-
r"""t200c_probe_battle_ab.py — 探测 battle AB 里能否读到能力 prefab 的 `_preDelay`（T-200c）

目的（04/71 §6 缺口①）：普攻前摇 `AbstractAnimatedAbility._preDelay //0x180` 是 prefab
序列化字段，本地 JSON 表没有。本脚本检查已备份的 battle AB 是否可解析出该字段。

用法：
    python t200c_probe_battle_ab.py <ab 路径> [--list] [--grep 0.4,0.4667]
"""
from __future__ import annotations

import argparse
import os
import struct
import sys

sys.stdout.reconfigure(encoding='utf-8')

CLIENT_RES = r'E:\__file\ak_kb\client_res'
TOOLS = r'C:\Users\23922\Documents\ds_harness\ak\code\tools'


def _register_lz4ak():
    """★关键：明日方舟的 bundle 压缩标记是 LZHAM，实际算法是 **LZ4AK**（token 高低 4 位互换的 LZ4）。

    工作区已有 `ak\code\tools\ak_lz4ak.py`（源自 Ark-Unpacker，BSD-3）。
    注册后 UnityPy 即可直读（见 `knowledge/04/15`、`04/30`）。
    """
    import UnityPy
    from UnityPy.enums import CompressionFlags
    from UnityPy.helpers import CompressionHelper as C
    if TOOLS not in sys.path:
        sys.path.insert(0, TOOLS)
    from ak_lz4ak import decompress_lz4ak
    C.DECOMPRESSION_MAP[CompressionFlags.LZHAM] = decompress_lz4ak
    return UnityPy


def scan_ab(path: str, list_limit: int = 30, want: list[float] | None = None):
    UnityPy = _register_lz4ak()
    env = UnityPy.load(path)
    print(f'=== {os.path.basename(path)} （{os.path.getsize(path)} B）===')
    counts: dict[str, int] = {}
    names: list[str] = []
    mb_raw: list[tuple[str, bytes]] = []
    for obj in env.objects:
        t = obj.type.name
        counts[t] = counts.get(t, 0) + 1
        if t in ('MonoBehaviour', 'GameObject'):
            try:
                d = obj.read()
                nm = getattr(d, 'm_Name', None) or getattr(d, 'name', None) or ''
                if nm:
                    names.append(f'{t}:{nm}')
                if t == 'MonoBehaviour':
                    raw = getattr(d, 'm_RawData', None) or obj.get_raw_data()
                    if raw:
                        mb_raw.append((str(nm), raw))
            except Exception:
                pass
    print('对象类型统计:', counts)
    print(f'命名对象（前 {list_limit}）:')
    for n in names[:list_limit]:
        print('   ', n)

    # --- 在 MonoBehaviour 原始字节里找候选 float ---
    if want:
        print(f'\n在 {len(mb_raw)} 个 MonoBehaviour 原始数据里搜候选 float: {want}')
        hits = 0
        for nm, raw in mb_raw:
            for target in want:
                b = struct.pack('<f', target)
                idx = raw.find(b)
                if idx >= 0:
                    hits += 1
                    if hits <= 20:
                        print(f'   命中 {target} @ {os.path.basename(path)}::{nm or "(无名)"} +0x{idx:x}')
        print(f'  命中总数 {hits}')
    return names, mb_raw


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('ab')
    ap.add_argument('--list', type=int, default=30)
    ap.add_argument('--grep', default='')
    a = ap.parse_args()
    want = [float(x) for x in a.grep.split(',') if x.strip()] if a.grep else None
    p = a.ab if os.path.isabs(a.ab) else os.path.join(CLIENT_RES, a.ab)
    scan_ab(p, a.list, want)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
