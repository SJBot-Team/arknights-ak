# -*- coding: utf-8 -*-
"""T-200h：从客户端 AB 里**取值**：`_preDelay` / `_delayToBorn` / `steeringFactor` /
`maxSteeringForce` / `_timeMode` / `_cooldown` 等 prefab 序列化字段。

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

FIELD_SETS = {
    'ability': ('_preDelay', '_timeMode', '_cooldown', '_maxAnimScale', '_animKey',
                '_waitForAttackEvent', '_resetCdStrategy', '_preDelayFactor',
                '_recalculatePlaybackSpeed', '_selectTargetTiming', '_minPostDelay'),
    'move': ('_steeringFactor', '_maxSteeringForce'),
    'enemy': ('_delayToBorn', '_onlyDelayToBornOnTileStart', '_blockVolume',
              '_lifePointReduce'),
}


def probe(path, want_go=None):
    try:
        env = UnityPy.load(path)
    except Exception as e:                                       # noqa: BLE001
        print(f'!! {os.path.basename(path)}: {e}')
        return
    print(f'\n########## {os.path.basename(path)} ##########')
    # 1) 找到目标 GameObject 与其组件（含子对象）
    go_ids = set()
    go_names = {}
    for obj in env.objects:
        if obj.type.name != 'GameObject':
            continue
        try:
            d = obj.read()
        except Exception:                                        # noqa: BLE001
            continue
        if want_go and d.m_Name in want_go:
            go_ids.add(obj.path_id)
            go_names[obj.path_id] = d.m_Name
    if want_go:
        print(f'GO 命中: {go_names}')
        # 收集组件的 MonoBehaviour 字段（只对命中 GO 直接挂的）
        for obj in env.objects:
            if obj.type.name != 'GameObject':
                continue
            try:
                d = obj.read()
            except Exception:                                    # noqa: BLE001
                continue
            if d.m_Name not in want_go:
                continue
            print(f'--- {d.m_Name} 组件:')
            for c in (getattr(d, 'm_Component', None) or []):
                try:
                    cc = c.component.read()
                except Exception:                                # noqa: BLE001
                    continue
                tn = type(cc).__name__
                if tn != 'MonoBehaviour':
                    if tn in ('CapsuleCollider2D', 'CircleCollider2D', 'BoxCollider2D'):
                        print(f'      {tn}: r={getattr(cc,"m_Radius",None)} '
                              f'off={getattr(cc,"m_Offset",None)} trig={getattr(cc,"m_IsTrigger",None)}')
                    continue
                try:
                    tt = cc.read_typetree()
                except Exception:                                # noqa: BLE001
                    tt = {}
                hit = {k: v for k, v in (tt or {}).items()
                       if any(k in fs for fs in FIELD_SETS.values())}
                if hit:
                    nm = tt.get('m_Name') or ''
                    print(f'      MB({nm!r}) {hit}')
    # 2) 全库统计：每种字段的取值分布（对全 prefab 扫描）
    stats: dict[str, dict] = {}
    for obj in env.objects:
        if obj.type.name != 'MonoBehaviour':
            continue
        try:
            tt = obj.read_typetree()
        except Exception:                                        # noqa: BLE001
            continue
        if not isinstance(tt, dict):
            continue
        for fs in FIELD_SETS.values():
            for k in fs:
                if k in tt and tt[k] is not None:
                    stats.setdefault(k, {})
                    key = str(tt[k])
                    stats[k][key] = stats[k].get(key, 0) + 1
        if len(stats) >= 30 and sum(len(v) for v in stats.values()) > 400:
            pass
    for k in sorted(stats):
        pairs = sorted(stats[k].items(), key=lambda kv: -kv[1])[:14]
        print(f'  [{k}] 取值分布(top14): {pairs}')


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'enm'
    if target == 'enm':
        p = r'E:\__file\ak_kb\client_res\enm_pfb\enm_pfb_0.ab'
        probe(p, want_go={'enemy_1000_gopro', 'enemy_1000_gopro_2'})
        p2 = r'E:\__file\ak_kb\client_res\enm_pfb\enm_pfb_base_0.ab'
        probe(p2, want_go={'enemy_1000_gopro', 'enemy_1000_gopro_2'})
    else:
        for fn in sorted(os.listdir(target)):
            if fn.endswith('.ab') and 'char_123_fang' in fn:
                probe(os.path.join(target, fn), want_go=None)
