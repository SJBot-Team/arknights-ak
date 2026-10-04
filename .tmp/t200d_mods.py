import json, os, sys, re
sys.stdout.reconfigure(encoding='utf-8')
OUT = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'
st = json.loads(open(os.path.join(OUT,'t200d_initial_state.json'), encoding='utf-8').read())
det = st['detail']
print('TYPE', det.get('type'))
print('BASIC', json.dumps(det['basic'], ensure_ascii=False, indent=1)[:3000])
mods = det['modules']
print('N MODULES', len(mods))
for i,m in enumerate(mods):
    print('== MOD', i, m.get('module_type'), list(m.keys()))
    if m.get('module_type') == 'MODULE_TYPE_CONTENT':
        for j,p in enumerate(m.get('paragraphs', [])):
            print('  -- PARA', j, p.get('para_type'), list(p.keys()))
            if p.get('para_type') == 1:
                print('     TEXT:', json.dumps(p.get('text'), ensure_ascii=False)[:1500])
            elif p.get('para_type') == 2:
                print('     PIC:', json.dumps(p.get('pic'), ensure_ascii=False)[:1200])
            else:
                print('     OTHER:', json.dumps(p, ensure_ascii=False)[:800])
