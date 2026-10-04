# -*- coding: utf-8 -*-
"""calls.py —— 列出某方法（或其类全部方法）调用了什么，紧凑输出。

用法: python calls.py <method-substring> [--depth N] [--all]
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
import mono_il
from mono_il import Asm, CALL_OPS

DLL = r'D:\__soft\ak\ArknightR\ArknightR_Data\Managed\Assembly-CSharp.dll'


def main():
    A = Asm(DLL)
    pat = sys.argv[1]
    depth = 1
    if '--depth' in sys.argv:
        depth = int(sys.argv[sys.argv.index('--depth') + 1])
    ms = A.find_methods(pat)
    if not ms:
        print('no method matches', pat); return
    seen = set()

    def walk(rid, d, ind):
        name = A.caller_name(rid)
        print('  ' * ind + f'[{rid}] {name}  : {A.method_by_rid[rid].get("sig")}')
        if d <= 0:
            return
        ins = A.disasm(rid) or []
        cs = []
        for off, nm, txt in ins:
            if nm in CALL_OPS and txt and not txt.startswith('<'):
                if txt not in cs:
                    cs.append(txt)
        for c in cs:
            sub = A.find_methods(c + '$')
            # 精确匹配
            exact = None
            for m in A.methods:
                if A.caller_name(m['rid']) == c:
                    exact = m['rid']; break
            if exact is None:
                print('  ' * (ind + 1) + c + '   (external / 未在库内)')
                continue
            if exact in seen:
                print('  ' * (ind + 1) + f'[{exact}] {c}   (已展开)')
                continue
            seen.add(exact)
            walk(exact, d - 1, ind + 1)

    for m in ms[:6]:
        seen.clear()
        walk(m['rid'], depth, 0)
        print()


main()
