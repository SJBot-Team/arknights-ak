# -*- coding: utf-8 -*-
"""T-200h：在客户端 AB（enm_pfb_*.ab / charpack）里找 `_preDelay` / `_delayToBorn` /
`steeringFactor` / `maxSteeringForce` 等 prefab 序列化字段的**真值**。

只读 E 盘；不启动模拟器/游戏。
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

DIRS = [r'E:\__file\ak_kb\client_res\enm_pfb', r'E:\__file\ak_kb\client_res']
WANT_GO = {'enemy_1000_gopro', 'enemy_1000_gopro_2'}
KEYS = ('preDelay', 'delayToBorn', 'steeringFactor', 'maxSteeringForce',
        'attackTime', 'animScale', 'timeMode')


def scan(path, only_go=None):
    try:
        env = UnityPy.load(path)
    except Exception as e:                                       # noqa: BLE001
        print(f'  !! load fail {os.path.basename(path)}: {e}')
        return
    types = {}
    monos = []
    gos = {}
    for obj in env.objects:
        tn = obj.type.name
        types[tn] = types.get(tn, 0) + 1
        if tn == 'GameObject' and only_go:
            try:
                d = obj.read()
            except Exception:                                    # noqa: BLE001
                continue
            if d.m_Name in only_go:
                gos[d.m_Name] = obj.path_id
        if tn == 'MonoBehaviour':
            monos.append(obj)
    print(f'== {os.path.basename(path)}  types={types}')
    if only_go:
        print(f'   GO hit: {gos}')
    n = 0
    for obj in monos:
        try:
            d = obj.read()
        except Exception:                                        # noqa: BLE001
            continue
        nm = getattr(d, 'm_Name', '') or ''
        fields = {}
        try:
            tt = d.read_typetree()
        except Exception:                                        # noqa: BLE001
            tt = None
        if isinstance(tt, dict):
            for k, v in tt.items():
                kl = k.lower()
                if any(w.lower() in kl for w in KEYS):
                    fields[k] = v
        if fields:
            n += 1
            print(f'   [{n}] objid={obj.path_id} name={nm!r} script={getattr(getattr(d,"m_Script",None),"path_id",None)}')
            for k, v in fields.items():
                print(f'        {k} = {v}')
        if n > 40:
            print('   ...(截断)')
            break
    if n == 0:
        # 打印一个 MonoBehaviour 的全部字段名，便于后续按名找
        for obj in monos[:1]:
            try:
                tt = obj.read_typetree()
            except Exception:                                    # noqa: BLE001
                continue
            print('   样本 MonoBehaviour 字段名:', list(tt.keys())[:60])


if __name__ == '__main__':
    files = []
    for d in DIRS:
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if fn.endswith('.ab'):
                files.append(os.path.join(d, fn))
    print(f'共 {len(files)} 个 .ab')
    for p in files:
        scan(p, only_go=WANT_GO if 'enm_pfb' in p else None)
