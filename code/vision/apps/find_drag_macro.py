# -*- coding: utf-8 -*-
"""find_drag_macro.py — 在所有 MuMu 键鼠方案里找**含"拖拽/鼠标曲线"的宏动作**。

## 背景（D1）
"落格提交"在所有注入通道上都失败（ADB tap / motionevent UP / swipe、SendMessage、
PostMessage 鼠标拖拽、宏键 `click_rel:mouse` 点击）。
**宏 `click_rel:mouse` 只做"点击"，只会取消拖拽** ⇒ 应寻找**真正做拖拽**的动作
（`curve_rel` / `drag` / `mouse_down`+`mouse_move`+`mouse_up` 之类，即"划火柴"本体）。

## 结构（已探明）
顶层 `{info, keymaps, param}`；`keymaps` 是**列表**，元素是**字典**（一组按键），
每个字典的 **value** 才是按键条目：`{key:{...}, press_actions:[...], release_actions:[...]}`。

用法：python find_drag_macro.py [关键字...]     默认关键字 = mouse curve drag 拖 划
"""
from __future__ import annotations

import glob
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

KM_DIR = os.path.join(os.environ['APPDATA'], 'Netease', 'MuMuPlayer', 'data', 'keymapConfig')
KW = sys.argv[1:] or ['mouse', 'curve', 'drag', '划', '拖']


def entries(kms):
    """把 `keymaps` 展开成条目列表。"""
    out = []
    for g in kms or []:
        if isinstance(g, dict):
            for v in g.values():
                if isinstance(v, dict):
                    out.append(v)
                elif isinstance(v, list):
                    out.extend(x for x in v if isinstance(x, dict))
        elif isinstance(g, list):
            out.extend(x for x in g if isinstance(x, dict))
    return out


def main() -> int:
    pats = [os.path.join(KM_DIR, 'com.hypergryph.arknights*.json')]
    files = sorted(f for p in pats for f in glob.glob(p))
    print(f'方案文件 {len(files)} 个（当前游戏包 com.hypergryph.arknights）\n')
    hits = 0
    for f in files:
        try:
            d = json.load(open(f, encoding='utf-8'))
        except Exception:                                       # noqa: BLE001
            continue
        es = entries(d.get('keymaps'))
        found = []
        for e in es:
            acts = list(e.get('press_actions') or []) + list(e.get('release_actions') or [])
            s = ' '.join(str(a) for a in acts)
            if any(k.lower() in s.lower() for k in KW):
                found.append((e.get('key', {}).get('text'), acts))
        if found:
            hits += 1
            print(f'── {os.path.basename(f)}  （{len(es)} 条，命中 {len(found)}）')
            for txt, acts in found[:14]:
                print(f'   键={txt!r:<6} {" | ".join(str(a) for a in acts)[:190]}')
            print()
    if not hits:
        print(f'未找到含 {KW} 的条目')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
