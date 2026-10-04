# -*- coding: utf-8 -*-
"""read_enemy_colliders.py — ★用 UnityPy **直接读客户端 prefab** 的逐敌碰撞半径（可信数据源）。

## 背景
用户指出：**「受击半径不同的单位符合玩家认知，但猎狗 0.8 半径与玩家游戏常识不符，请给出可信的数据来源」**
⇒ 此前的 0.8 是**从单条标定事件反推的拟合值**，不是数据，必须被客户端数据替代或推翻。

## 数据源
`E:\\__file\\ak_kb\\client_res\\enm_pfb\\enm_pfb_N.ab`（客户端 AB，只读备份），
其中每个敌人一个 GameObject，含 `CircleCollider2D.m_Radius` / `CapsuleCollider2D`。

## 做法
遍历各 `enm_pfb_*.ab`，列出**每个根对象名**与其下所有碰撞体的类型/半径/尺寸/偏移。
"""
from __future__ import annotations

import glob
import os
import re
import sys

sys.path.insert(0, r'C:\Users\23922\Documents\ds_harness\ak\scripts')
# ★关键：明日方舟的 AB 用 **LZ4AK 变体（Unity 报为 LZHAM）** 压缩，
#   UnityPy 自带的 LZHAM 解码器已移除 ⇒ 必须注册本仓库的 `ak_lz4ak.decompress_lz4ak`
#   （此前生成 `collider_report.json` 的 `scripts/inspect_prefab.py` 正是这么做的）。
from UnityPy.enums.BundleFile import CompressionFlags          # noqa: E402
from UnityPy.helpers import CompressionHelper                   # noqa: E402
from ak_lz4ak import decompress_lz4ak                           # noqa: E402

CompressionHelper.DECOMPRESSION_MAP[CompressionFlags.LZHAM] = decompress_lz4ak

import UnityPy                                                  # noqa: E402

sys.stdout.reconfigure(encoding='utf-8')

DIRS = [r'E:\__file\ak_kb\client_res\enm_pfb', r'E:\__file\ak_kb\client_res']
WANT = re.compile(r'gopro', re.I)


def dump_bundle(path: str, only=None, max_show=8):
    env = UnityPy.load(path)
    rows = []
    for obj in env.objects:
        if obj.type.name not in ('GameObject', 'MonoBehaviour'):
            continue
        try:
            data = obj.read()
        except Exception:                                        # noqa: BLE001
            continue
        nm = getattr(data, 'm_Name', None) or getattr(data, 'name', None) or ''
        # 收集该对象自身/其组件的碰撞体
        coll = []
        if obj.type.name == 'GameObject':
            for comp in (getattr(data, 'm_Component', None) or []):
                try:
                    c = comp.component.read()
                except Exception:                                # noqa: BLE001
                    continue
                t = type(c).__name__
                if 'Collider2D' in t:
                    coll.append((t, getattr(c, 'm_Radius', None),
                                 getattr(c, 'm_Size', None),
                                 getattr(c, 'm_Offset', None)))
        if coll:
            rows.append((nm, coll))
    return rows


def main() -> int:
    files = []
    for d in DIRS:
        files += sorted(glob.glob(os.path.join(d, 'enm_pfb_*.ab')))
    files = sorted(set(files))
    print(f'找到 {len(files)} 个 enm_pfb bundle')
    hit_any = False
    for p in files:
        try:
            rows = dump_bundle(p)
        except Exception as ex:                                  # noqa: BLE001
            print(f'  {os.path.basename(p)}: 解析失败 {ex!r}')
            continue
        hits = [(nm, c) for nm, c in rows if WANT.search(nm)]
        if hits:
            hit_any = True
            print(f'\n=== {os.path.basename(p)} （共 {len(rows)} 个带碰撞体的对象）===')
            for nm, coll in hits:
                print(f'  {nm}:')
                for t, r, s, o in coll:
                    extra = f'radius={r}' if r is not None else f'size={s}'
                    print(f'      {t}  {extra}  offset={o}')
        elif rows:
            print(f'  {os.path.basename(p)}: {len(rows)} 个对象，例 {rows[0][0]!r}')
    if not hit_any:
        print('\n未在本地 bundle 中找到 gopro —— 可能其 prefab 在未下载的 bundle 中（需查 hot_update_list）')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
