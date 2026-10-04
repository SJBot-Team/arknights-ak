# -*- coding: utf-8 -*-
"""dump_keymap2.py — 正确展开 MuMu 键鼠方案，打印**动作词表**与指定按键条目。

结构（已修正）：`keymaps` 是**列表**；元素可能是 **dict**，其 **values** 才是条目，
条目形如 `{key:{device,scan_code,text,virtual_key}, press_actions:[...], release_actions:[...],
           rel_work_position:{...}, icon:{...}}`；也可能条目**直接**出现在列表里。

用法：python dump_keymap2.py <方案json> [按键字母…]
"""
from __future__ import annotations

import collections
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')


def walk(node, out):
    """递归收集所有形如"按键条目"的字典。"""
    if isinstance(node, dict):
        if 'key' in node and ('press_actions' in node or 'release_actions' in node):
            out.append(node)
            return
        for v in node.values():
            walk(v, out)
    elif isinstance(node, list):
        for v in node:
            walk(v, out)


def main() -> int:
    p = sys.argv[1]
    want = [a.upper() for a in sys.argv[2:]] or ['F']
    d = json.load(open(p, encoding='utf-8'))
    es = []
    walk(d.get('keymaps'), es)
    print(f'{p.split(chr(92))[-1]}: 条目 {len(es)} 条')
    vocab = collections.Counter()
    for e in es:
        for a in list(e.get('press_actions') or []) + list(e.get('release_actions') or []):
            vocab[str(a).split(':')[0]] += 1
    print('动作词表:', dict(vocab.most_common(20)))
    print()
    for e in es:
        t = str((e.get('key') or {}).get('text') or '')
        if any(w == t.upper() for w in want):
            print(f"键 {t!r}  scan={(e.get('key') or {}).get('scan_code')} "
                  f"vk={(e.get('key') or {}).get('virtual_key')}")
            print('  按下:', ' | '.join(str(a) for a in (e.get('press_actions') or [])))
            if e.get('release_actions'):
                print('  抬起:', ' | '.join(str(a) for a in e['release_actions']))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
