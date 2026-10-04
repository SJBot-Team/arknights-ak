# -*- coding: utf-8 -*-
"""export_all_enemy_radii.py — ★批量导出**客户端实测**的全体敌人碰撞体数据（可信数据源）。

## 产出
`ak/data/derived/enemy_colliders.json`：
```
{ "_doc": …, "source": {…},
  "enemies": { "enemy_1000_gopro": {"name":…, "colliders":[{"type","radius","offset","is_trigger"}]},
               … },
  "by_radius": { "0.1": [ …敌人id… ], … } }
```

## 方法（可复现）
UnityPy 1.25.3 + 本仓库 `scripts/ak_lz4ak.py` 的 LZ4AK 解压器
（明日方舟 AB 用 LZ4AK 变体压缩，Unity 报为 LZHAM；不注册该解压器会报
 `Custom compression or unimplemented LZHAM`）。

## 覆盖度说明
本地仅备份了 `client_res/enm_pfb/enm_pfb_*.ab`（约 38 块），
**并非全集**（游戏内敌人 prefab 总数为数千）⇒ 本表只覆盖已备份部分，缺者**标为待补**。
"""
from __future__ import annotations

import glob
import json
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
OUT = r'C:\Users\23922\Documents\ds_harness\ak\data\derived\enemy_colliders.json'


def colliders_of(obj) -> list[dict]:
    d = obj.read()
    out = []
    for c in (getattr(d, 'm_Component', None) or []):
        try:
            cc = c.component.read()
        except Exception:                                        # noqa: BLE001
            continue
        tn = type(cc).__name__
        if 'Collider2D' not in tn:
            continue
        rec = {'type': tn}
        if hasattr(cc, 'm_Radius'):
            rec['radius'] = round(float(cc.m_Radius), 6)
        if hasattr(cc, 'm_Size'):
            s = cc.m_Size
            rec['size'] = [round(float(getattr(s, 'x', 0)), 6),
                           round(float(getattr(s, 'y', 0)), 6)]
        if hasattr(cc, 'm_Offset'):
            o = cc.m_Offset
            rec['offset'] = [round(float(getattr(o, 'x', 0)), 6),
                             round(float(getattr(o, 'y', 0)), 6)]
        if hasattr(cc, 'm_IsTrigger'):
            rec['is_trigger'] = bool(cc.m_IsTrigger)
        out.append(rec)
    return out


def main() -> int:
    files = []
    for d in DIRS:
        files += glob.glob(os.path.join(d, 'enm_pfb_*.ab'))
    files = sorted(set(files))
    print(f'扫描 {len(files)} 个 bundle')
    enemies: dict[str, dict] = {}
    bundles_ok, bundles_fail = 0, 0
    for p in files:
        try:
            env = UnityPy.load(p)
            n_here = 0
            for obj in env.objects:
                if obj.type.name != 'GameObject':
                    continue
                try:
                    nm = obj.read().m_Name
                except Exception:                                # noqa: BLE001
                    continue
                if not nm or not nm.startswith('enemy_'):
                    continue
                cols = colliders_of(obj)
                if not cols:
                    continue
                enemies[nm] = {'bundle': os.path.basename(p), 'colliders': cols}
                n_here += 1
            bundles_ok += 1
            print(f'  {os.path.basename(p):<22} 敌人对象 {n_here}')
        except Exception as ex:                                  # noqa: BLE001
            bundles_fail += 1
            print(f'  {os.path.basename(p):<22} 解析失败 {type(ex).__name__}')
    by_radius: dict[str, list] = {}
    for nm, rec in enemies.items():
        for c in rec['colliders']:
            if c['type'] == 'CircleCollider2D':
                by_radius.setdefault(str(c.get('radius')), []).append(nm)
    data = {
        '_doc': '客户端 prefab 实测的敌人碰撞体（可信数据源；只读本机客户端 AB 备份）',
        'source': {
            'method': 'UnityPy 1.25.3 + CompressionHelper.DECOMPRESSION_MAP[LZHAM]=ak_lz4ak.decompress_lz4ak',
            'script': 'ak/scripts/export_all_enemy_radii.py',
            'bundles': os.path.basename(DIRS[0]) + '/enm_pfb_*.ab',
        },
        'coverage': {'bundles_total': len(files), 'bundles_ok': bundles_ok,
                     'bundles_fail': bundles_fail, 'enemies': len(enemies),
                     'note': '**并非全集**（游戏内敌人 prefab 数千）⇒ 未覆盖者标为待补'},
        'enemies': enemies,
        'by_radius': {k: sorted(v) for k, v in sorted(by_radius.items())},
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(data, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'\n已导出 {OUT}')
    print(f'  敌人 {len(enemies)} 个；bundle 成功 {bundles_ok}/失败 {bundles_fail}')
    print('  半径分布（CircleCollider2D）：')
    for r, lst in sorted(by_radius.items(), key=lambda kv: float(kv[0])):
        print(f'    {r:>6} : {len(lst):>4} 个   例 {lst[:3]}')
    for k in ('enemy_1000_gopro', 'enemy_1000_gopro_2', 'enemy_1000_gopro_3'):
        if k in enemies:
            print(f'  ★{k}: {enemies[k]["colliders"]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
