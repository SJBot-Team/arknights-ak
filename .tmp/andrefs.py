# -*- coding: utf-8 -*-
"""andrefs.py —— 找"同时引用多个 token 子串"的方法（交集检索）。混淆代码下的主武器。

用法: python andrefs.py "<子串1>" "<子串2>" ["<子串3>" ...] [--class PREFIX]
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from mono_il import Asm

DLL = r'D:\__soft\ak\ArknightR\ArknightR_Data\Managed\Assembly-CSharp.dll'


def main():
    kws = [a for a in sys.argv[1:] if not a.startswith('--')]
    cls = None
    if '--class' in sys.argv:
        cls = sys.argv[sys.argv.index('--class') + 1]
    A = Asm(DLL)
    per = []
    for k in kws:
        per.append(A.refs(k, limit=100000))
    sets = []
    for lst in per:
        s = {}
        for txt, callers in lst:
            for c in callers:
                s.setdefault(c, []).append(txt)
        sets.append(s)
    common = set(sets[0])
    for s in sets[1:]:
        common &= set(s)
    if cls:
        common = {c for c in common if c.startswith(cls)}
    print(f'== 交集 {kws}  命中 {len(common)} 个方法 ==')
    for c in sorted(common):
        detail = []
        for i, s in enumerate(sets):
            detail.append(f'{kws[i]}:' + ','.join(sorted(set(s[c]))[:3]))
        print(f'  {c}')
        print('      ' + ' | '.join(detail))


main()
