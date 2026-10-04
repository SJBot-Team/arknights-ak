# -*- coding: utf-8 -*-
import os, sys, re, json, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import UnityPy

E = r'E:\__file\ak\ArknightR\ArknightR_Data'
DD = r'D:\__soft\ak\ArknightR\ArknightR_Data'
def hr(t): print('\n' + '=' * 24 + ' ' + t + ' ' + '=' * 24)

hr('2. BuffData JSONL sample lines')
p = None
for r, dd, ff in os.walk(os.path.join(E, 'StreamingAssets', 'aa', 'StandaloneWindows64')):
    for f in ff:
        if f.startswith('buffdata_b280d'):
            p = os.path.join(r, f)
print('bundle:', p)
env = UnityPy.load(p)
for o in env.objects:
    if o.type.name == 'TextAsset':
        raw = o.read().m_Script
        if isinstance(raw, str):
            raw = raw.encode('utf-8', 'replace')
        txt = raw.decode('utf-8', 'replace')
        lines = [x for x in txt.split('\n') if x.strip()]
        print('JSONL 行数:', len(lines))
        for ln in lines[:12]:
            print('   ', ln[:200])
        print('   ... 末行:', lines[-1][:200])
        keys = collections.Counter()
        for ln in lines:
            try:
                for k in json.loads(ln).keys():
                    keys[k] += 1
            except Exception:
                pass
        print('   字段出现次数 top 30:', keys.most_common(30))
        print('   一行最多字段数:', max((len(json.loads(l)) for l in lines if l.strip()), default=0))

hr('3. E: vs D: distribution')
for tag, root in (('E:', r'E:\__file\ak\ArknightR'), ('D:', r'D:\__soft\ak\ArknightR')):
    n = 0; sz = 0
    dirs = collections.Counter(); dsz = collections.Counter()
    for r, dd, ff in os.walk(root):
        for f in ff:
            fp = os.path.join(r, f)
            n += 1
            s = os.path.getsize(fp); sz += s
            rel = os.path.relpath(r, root)
            if rel.count(os.sep) <= 3:
                dirs[rel] += 1; dsz[rel] += s
    print('\n%s files=%d total=%.1fMB' % (tag, n, sz / 1048576))
    for k, v in dirs.most_common(16):
        print('    %-64s %5d %8.1fMB' % (k, v, dsz[k] / 1048576))
    print('    MonoBleedingEdge:', os.path.isdir(os.path.join(root, 'MonoBleedingEdge')),
          '| StreamingAssets/aa:', os.path.isdir(os.path.join(root, 'ArknightR_Data', 'StreamingAssets', 'aa')))
    try:
        env = UnityPy.load(os.path.join(root, 'ArknightR_Data', 'globalgamemanagers'))
        for o in env.objects:
            if o.type.name == 'PlayerSettings':
                d = o.read_typetree()
                print('    productName=%r bundleVersion=%r' % (d.get('productName'), d.get('bundleVersion')))
    except Exception as e:
        print('    ggm err', e)

hr('4. D: bundle dir census')
D2 = os.path.join(DD, 'StreamingAssets', 'aa', 'StandaloneWindows64')
cnt = collections.Counter(); s2 = collections.Counter()
for r, dd, ff in os.walk(D2):
    for f in ff:
        if f.endswith('.bundle'):
            rel = os.path.relpath(r, D2).replace('defaultlocalgroup_assets_assets', 'DLG')
            cnt[rel] += 1; s2[rel] += os.path.getsize(os.path.join(r, f))
for k, v in cnt.most_common():
    print('    %-48s %5d bundles %8.1f MB' % (k, v, s2[k] / 1048576))

hr('5. E: copy - any char/enemy/unit/spine bundles?')
names = []
for r, dd, ff in os.walk(os.path.join(E, 'StreamingAssets', 'aa', 'StandaloneWindows64')):
    for f in ff:
        if f.endswith('.bundle'):
            names.append(f)
for pat in ('char_', 'enemy_', 'spine', 'unit', 'token', 'trap', 'common', 'skill', 'buff'):
    hit = [n for n in names if n.startswith(pat)]
    print('  %-8s startswith -> %-4d sample=%s' % (pat, len(hit), hit[:4]))
print('  total', len(names))
