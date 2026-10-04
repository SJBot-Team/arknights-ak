# -*- coding: utf-8 -*-
"""Final verification: Type-column -> class-name mapping, D: vs E: distribution, misc."""
import os, sys, re, json, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import dotnet_md, UnityPy

E = r'E:\__file\ak\ArknightR\ArknightR_Data'
DD = r'D:\__soft\ak\ArknightR\ArknightR_Data'
def hr(t): print('\n' + '='*24 + ' ' + t + ' ' + '='*24)

md, _ = dotnet_md.parse(os.path.join(E, 'Managed', 'Assembly-CSharp.dll'), want_methods=False)
cls = collections.defaultdict(set)
for ns_, n_ in md['typedefs']:
    cls[ns_].add(n_)

hr('1. Type-column -> C# class name mapping test')
import openpyxl
wb = openpyxl.load_workbook(os.path.join(E, 'StreamingAssets', 'battle.xlsx'), read_only=True, data_only=True)
for sheet, ns_, col in (('BuffData', 'Buffs', 'Type'), ('SkillData', 'Skills', 'Type'),
                        ('UnitData', 'Units', 'Type'), ('BulletData', 'Bullets', 'Type'),
                        ('ModifyData', 'Modifys', 'Type')):
    ws = wb[sheet]
    rows = list(ws.iter_rows(values_only=True))
    # header row 2 (index 1) = field names
    hdr = [str(x) if x is not None else '' for x in rows[1]]
    try:
        ci = hdr.index(col)
    except ValueError:
        print('[%s] no %r column; header=%s' % (sheet, col, hdr[:24])); continue
    vals = collections.Counter(str(r[ci]).strip() for r in rows[3:] if r[ci] is not None and str(r[ci]).strip())
    types = cls.get(ns_, set())
    hit = [v for v in vals if v in types]
    miss = [v for v in vals if v not in types]
    print('\n[%s] %s 列去重值=%d ; 与 %s.* 类名完全匹配=%d' % (sheet, col, len(vals), ns_, len(hit)))
    print('   匹配上的 Type 值 (前40):', sorted(hit)[:40])
    print('   未匹配的 Type 值 (前25):', sorted(miss)[:25])
    print('   %s.* 类总数=%d' % (ns_, len(types)))
wb.close()

hr('2. sample data rows showing Type -> behaviour')
for b in ('buffdata_b280d244257e7c147301361fd609c0df.bundle',):
    p = None
    for root, dirs, files in os.walk(os.path.join(E, 'StreamingAssets', 'aa', 'StandaloneWindows64')):
        for f in files:
            if f == b: p = os.path.join(root, f)
    env = UnityPy.load(p)
    for o in env.objects:
        if o.type.name == 'TextAsset':
            raw = o.read().m_Script
            if isinstance(raw, str): raw = raw.encode('utf-8', 'replace')
            lines = raw.decode('utf-8', 'replace').split('\n')
            print('total JSONL lines:', len(lines))
            for ln in lines[:14]:
                print('   ', ln[:190])
            print('   ... last line:', lines[-2][:190] if len(lines) > 1 else '')

hr('3. E: vs D: distribution comparison')
for tag, root in (('E:', r'E:\__file\ak\ArknightR'), ('D:', r'D:\__soft\ak\ArknightR')):
    n = 0; sz = 0
    dirs = collections.Counter(); dsz = collections.Counter()
    for r, dd, ff in os.walk(root):
        for f in ff:
            fp = os.path.join(r, f)
            n += 1
            s = os.path.getsize(fp)
            sz += s
            rel = os.path.relpath(r, root)
            if rel.count(os.sep) <= 2:
                dirs[rel] += 1; dsz[rel] += s
    print('\n%s files=%d  total=%.1fMB' % (tag, n, sz/1048576))
    for k, v in dirs.most_common(14):
        print('    %-58s %5d  %8.1fMB' % (k, v, dsz[k]/1048576))
    print('    has MonoBleedingEdge:', os.path.isdir(os.path.join(root, 'MonoBleedingEdge')))
    print('    has StreamingAssets/aa:', os.path.isdir(os.path.join(root, 'ArknightR_Data', 'StreamingAssets', 'aa')))

hr('4. D: copy bundle dir census + does it carry units/spine?')
D2 = os.path.join(DD, 'StreamingAssets', 'aa', 'StandaloneWindows64')
cnt = collections.Counter(); s2 = collections.Counter()
for r, dd, ff in os.walk(D2):
    for f in ff:
        if f.endswith('.bundle'):
            rel = os.path.relpath(r, D2).replace('defaultlocalgroup_assets_assets', 'DLG')
            cnt[rel] += 1; s2[rel] += os.path.getsize(os.path.join(r, f))
for k, v in cnt.most_common():
    print('    %-46s %5d bundles %8.1f MB' % (k, v, s2[k]/1048576))
with open(os.path.join(DD, 'globalgamemanagers'), 'rb') as fh:
    pass
import UnityPy as UP
env = UP.load(os.path.join(DD, 'globalgamemanagers'))
for o in env.objects:
    if o.type.name == 'PlayerSettings':
        d = o.read_typetree()
        print('D: productName=%r bundleVersion=%r' % (d.get('productName'), d.get('bundleVersion')))

hr('5. E: copy - any Spine/units bundles at all?')
names = []
for r, dd, ff in os.walk(os.path.join(E, 'StreamingAssets', 'aa', 'StandaloneWindows64')):
    for f in ff:
        if f.endswith('.bundle'):
            names.append(f)
pats = ['char_', 'enemy_', 'spine', 'unit', 'token', 'trap']
for p in pats:
    hit = [n for n in names if n.startswith(p)]
    print('  %-8s startswith -> %d  sample=%s' % (p, len(hit), hit[:4]))
