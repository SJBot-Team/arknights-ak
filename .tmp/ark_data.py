# -*- coding: utf-8 -*-
"""ArknightR data pipeline: extract TextAssets, compare with battle.xlsx (read-only)."""
import os, sys, re, json, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import UnityPy, dotnet_md

E = r'E:\__file\ak\ArknightR\ArknightR_Data'
D2 = os.path.join(E, 'StreamingAssets', 'aa', 'StandaloneWindows64')
def hr(t): print('\n' + '='*24 + ' ' + t + ' ' + '='*24)

def allb():
    out = []
    for root, dirs, files in os.walk(D2):
        for f in files:
            if f.endswith('.bundle'):
                out.append(os.path.join(root, f))
    return out
B = allb()

def get_textasset(bundle):
    env = UnityPy.load(bundle)
    for o in env.objects:
        if o.type.name == 'TextAsset':
            d = o.read()
            raw = d.m_Script
            if isinstance(raw, str):
                raw = raw.encode('utf-8', 'replace')
            return d.m_Name, raw
    return None, None

hr('1. data/*.bundle -> TextAsset payloads')
for b in sorted(B):
    n = os.path.basename(b)
    if os.sep + 'data' + os.sep in b and 'maps' not in b:
        nm, raw = get_textasset(b)
        if raw is None:
            print('-- %s : no TextAsset' % n); continue
        print('\n-- %-46s TextAsset=%-16s %d bytes' % (n, nm, len(raw)))
        print('   head:', raw[:300])
        try:
            j = json.loads(raw.decode('utf-8'))
            if isinstance(j, list):
                print('   JSON list len=%d, item0 keys=%s' % (len(j), list(j[0].keys())[:30] if j and isinstance(j[0], dict) else j[:2]))
                if j and isinstance(j[0], dict):
                    print('   item0:', json.dumps(j[0], ensure_ascii=False)[:600])
            elif isinstance(j, dict):
                print('   JSON dict keys:', list(j.keys())[:30])
                k0 = list(j.keys())[0]
                print('   first value:', json.dumps(j[k0], ensure_ascii=False)[:600])
        except Exception as e:
            print('   not JSON:', type(e).__name__, str(e)[:80])

hr('2. maps bundle (1-11) full content')
for b in B:
    if os.sep + 'maps' + os.sep in b:
        nm, raw = get_textasset(b)
        print('-- %s -> %s' % (os.path.basename(b), nm))
        print(raw.decode('utf-8', 'replace')[:1800])
        break

hr('3. compare C# Buffs/Skills class names with battle.xlsx Id column')
md, _ = dotnet_md.parse(os.path.join(E, 'Managed', 'Assembly-CSharp.dll'), want_methods=False)
cls = collections.defaultdict(list)
for ns_, n_ in md['typedefs']:
    if ns_ in ('Buffs', 'Skills', 'Modifys', 'Bullets', 'Units'):
        cls[ns_].append(n_)
print({k: len(v) for k, v in cls.items()})
for k in ('Buffs', 'Modifys', 'Bullets', 'Units'):
    print('\n%s sample:' % k, cls[k][:40])

import openpyxl
wb = openpyxl.load_workbook(os.path.join(E, 'StreamingAssets', 'battle.xlsx'), read_only=True, data_only=True)
for sheet, key in (('BuffData', 'Buffs'), ('SkillData', 'Skills'), ('BulletData', 'Bullets'), ('UnitData', 'Units')):
    ws = wb[sheet]
    ids = []
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i < 3: continue
        v = row[0]
        if v is None or str(v).strip() in ('', '#'): 
            if len(ids) > 40: break
            continue
        if i > 4000: break
        ids.append(str(v).strip())
    cs = set(cls.get(key, []))
    inter = [x for x in ids if x in cs]
    print('\n[%s] xlsx Id 非空数=%d ; C# 类型数=%d ; 完全同名交集=%d' % (sheet, len(ids), len(cs), len(inter)))
    print('   xlsx Id 样例:', ids[:18])
    print('   交集样例:', inter[:18])
    missing = [x for x in ids[:200] if x not in cs]
    print('   xlsx 有而 C# 无 (前20):', missing[:20])
    extra = [x for x in list(cs)[:400] if x not in set(ids)]
    print('   C# 有而 xlsx 无 (前20):', extra[:20])
wb.close()

hr('4. raw strings around prts / torappu / arknights keywords in Assembly-CSharp.dll')
data = open(os.path.join(E, 'Managed', 'Assembly-CSharp.dll'), 'rb').read()
for kw in (b'prts', b'torappu', b'spine', b'.skel', b'.atlas', b'Arknight', b'arknight', b'excel', b'Excel', b'\xe7\x88\xac\xe5\x8f\x96'):
    for m in re.finditer(re.escape(kw), data):
        i = m.start()
        s = data[max(0, i-70):i+90]
        print('%-10s @%#x %r' % (kw[:9].decode('utf-8','replace'), i, s))
        break
hr('5. all ASCII strings containing prts/torappu/ab/导表 in Assembly-CSharp')
s = [x.decode('ascii') for x in re.findall(rb'[\x20-\x7e]{5,}', data)]
u = [x.decode('utf-16-le','replace') for x in re.findall(rb'(?:[\x20-\x7e]\x00){5,}', data)]
allstr = s + u
pat = re.compile(r'(prts|torappu|\.ab\b|spine|skel|atlas|arknight|导表|crawl|爬)', re.I)
seen = set()
for x in allstr:
    if pat.search(x) and x not in seen:
        seen.add(x); print('   ', x[:170])
