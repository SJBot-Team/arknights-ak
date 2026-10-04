# -*- coding: utf-8 -*-
"""ArknightR deep analysis: bundle contents + C# metadata (read-only)."""
import os, sys, re, json, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import dotnet_md

R = r'E:\__file\ak\ArknightR'
D = os.path.join(R, 'ArknightR_Data')
M = os.path.join(D, 'Managed')
def hr(t): print('\n' + '='*25 + ' ' + t + ' ' + '='*25)

hr('A. Assembly-CSharp.dll / firstpass - .NET metadata')
for name in ('Assembly-CSharp.dll', 'Assembly-CSharp-firstpass.dll'):
    p = os.path.join(M, name)
    md, _ = dotnet_md.parse(p, want_methods=True)
    print('\n### %s  size=%d md_version=%s streams=%s' % (name, md['size'], md.get('md_version'), md.get('streams')))
    print('cli dir', md.get('cli'), 'rowcounts', {hex(k): v for k, v in sorted(md.get('rowcounts', {}).items())})
    td = md.get('typedefs', [])
    print('TypeDef count', len(td))
    # group by namespace
    ns = collections.Counter(t[0] for t in td)
    print('namespaces:', ns.most_common(40))
    print('--- ALL types (ns.name) ---')
    for n, t in td:
        print('   %s%s' % (n + '.' if n else '', t))
    ms = md.get('methods', [])
    print('MethodDef count', len(ms))
    print('--- first 60 method names ---')
    print('   ', [m[0] for m in ms[:60]])
    us = md.get('userstrings', [])
    print('userstring count', len(us))
    chin = [s for s in us if re.search(r'[\u4e00-\u9fff]', s)]
    print('--- Chinese user strings (%d) ---' % len(chin))
    for s in chin[:200]:
        print('   ', s[:160])
    print('--- non-Chinese user strings sample (%d total) ---' % (len(us) - len(chin)))
    for s in [x for x in us if x not in chin][:120]:
        print('   ', s[:160])

hr('B. Addressable bundle content sampling')
import UnityPy
D2 = os.path.join(D, 'StreamingAssets', 'aa', 'StandaloneWindows64')
allb = []
for root, dirs, files in os.walk(D2):
    for f in files:
        if f.endswith('.bundle'):
            allb.append(os.path.join(root, f))
# pick one representative from several dirs
picks = []
seen = set()
for b in sorted(allb):
    rel = os.path.relpath(os.path.dirname(b), D2)
    key = rel
    if key not in seen:
        seen.add(key)
        picks.append(b)
# plus specific interesting ones
for pat in ('char_', 'enemy_', 'buff', 'skilldata', 'unitdata', 'battle', 'main_', 'data/buffdata'):
    for b in allb:
        if pat in os.path.basename(b):
            picks.append(b); break
print('dirs sampled:', len(picks))
for b in picks[:26]:
    try:
        env = UnityPy.load(b)
        kinds = collections.Counter()
        names = []
        for o in env.objects:
            kinds[o.type.name] += 1
            try:
                d = o.read()
                nm = getattr(d, 'm_Name', None) or getattr(d, 'name', None)
                if nm: names.append((o.type.name, nm))
            except Exception:
                pass
        print('\n-- %s  (%.1fKB)' % (os.path.relpath(b, D2), os.path.getsize(b)/1024))
        print('   objs:', dict(kinds))
        print('   names:', names[:14])
    except Exception as e:
        print('ERR', b, type(e).__name__, e)
