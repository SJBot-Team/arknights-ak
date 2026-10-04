# -*- coding: utf-8 -*-
"""Bundle content census + user string mining (read-only)."""
import os, sys, re, json, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import dotnet_md, UnityPy

DL = r'D:\__soft\ak\ArknightR\ArknightR_Data'
EL = r'E:\__file\ak\ArknightR\ArknightR_Data'
M = os.path.join(EL, 'Managed')

def hr(t): print('\n' + '=' * 25 + ' ' + t + ' ' + '=' * 25)

hr('0. bundle dir census (E: copy)')
D2 = os.path.join(EL, 'StreamingAssets', 'aa', 'StandaloneWindows64')
cnt = collections.Counter()
szs = collections.Counter()
for root, dirs, files in os.walk(D2):
    for f in files:
        if f.endswith('.bundle'):
            rel = os.path.relpath(root, D2).replace('defaultlocalgroup_assets_assets', 'DLG')
            cnt[rel] += 1
            szs[rel] += os.path.getsize(os.path.join(root, f))
for k, v in cnt.most_common():
    print('  %-40s %5d bundles  %8.1f MB' % (k, v, szs[k] / 1048576))

hr('1. object-type census across ALL bundles (E: copy) - sample 120')
allb = []
for root, dirs, files in os.walk(D2):
    for f in files:
        if f.endswith('.bundle'):
            allb.append(os.path.join(root, f))
import random
random.seed(7)
smp = random.sample(allb, min(120, len(allb)))
agg = collections.Counter()
errors = 0
for b in smp:
    try:
        env = UnityPy.load(b)
        for o in env.objects:
            agg[o.type.name] += 1
    except Exception as e:
        errors += 1
print('sampled', len(smp), 'parse errors', errors)
for k, v in agg.most_common():
    print('   %-22s %d' % (k, v))

hr('2. specific bundles: char_ / enemy_ / effect / spine')
targets = []
for pat in ('char_', 'enemy_1007', 'enemy_', 'asha', 'amiya'):
    for b in allb:
        n = os.path.basename(b)
        if n.startswith(pat) or pat in n:
            targets.append(b)
            break
for rel in ('bundles/units', 'bundles/spine', 'bundles/char', 'bundles/enemy'):
    for b in allb:
        if rel.replace('/', os.sep) in b:
            targets.append(b); break
seen = set()
for b in targets:
    if b in seen: continue
    seen.add(b)
    try:
        env = UnityPy.load(b)
        kinds = collections.Counter(o.type.name for o in env.objects)
        names = []
        for o in env.objects:
            try:
                d = o.read()
                nm = getattr(d, 'm_Name', None) or getattr(d, 'name', None)
                if nm: names.append(nm)
            except Exception: pass
        print('\n-- %s (%.1fKB)  -> %s' % (os.path.relpath(b, D2), os.path.getsize(b)/1024, dict(kinds)))
        print('   names:', names[:18])
        # check for spine / atlas textassets
        for o in env.objects:
            if o.type.name in ('TextAsset', 'MonoBehaviour'):
                try:
                    d = o.read()
                    nm = getattr(d, 'm_Name', '')
                    if o.type.name == 'TextAsset':
                        raw = d.m_Script if isinstance(d.m_Script, bytes) else str(d.m_Script).encode('utf-8','replace')
                        print('   TextAsset %r head=%r' % (nm, raw[:120]))
                    else:
                        print('   MonoBehaviour %r script=%s' % (nm, getattr(d, 'm_Script', None)))
                except Exception as e:
                    pass
    except Exception as e:
        print('ERR', b, e)

hr('3. user-string mining: URLs / file patterns / API')
for name in ('Assembly-CSharp.dll', 'Assembly-CSharp-firstpass.dll'):
    md, _ = dotnet_md.parse(os.path.join(M, name), want_methods=False)
    us = md.get('userstrings', [])
    print('\n### %s: %d user strings' % (name, len(us)))
    inter = [s for s in us if re.search(r'(http|www\.|\.json|\.xlsx|\.png|\.txt|\.csv|\.ab\b|\.skel|\.atlas|\.bytes|\\\\|/|api|Api|url|Url|URL|path|Path|file|File|dir|Dir)', s)]
    for s in inter[:250]:
        print('   ', s[:180])

hr('4. method names (business code) - Assembly-CSharp')
md, _ = dotnet_md.parse(os.path.join(M, 'Assembly-CSharp.dll'), want_methods=True)
ms = md.get('methods', [])
print('total methods', len(ms))
names = [m[0] for m in ms]
uniq = list(dict.fromkeys(names))
print('unique method names', len(uniq))
print(uniq[:900])
