import json, os, sys, re
sys.stdout.reconfigure(encoding='utf-8')
OUT = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'
st = json.loads(open(os.path.join(OUT,'t200d_initial_state.json'), encoding='utf-8').read())
mods = st['detail']['modules']
mc = mods[3]['module_content']
print('CONTENT KEYS', list(mc.keys()))
paras = mc.get('paragraphs') or []
print('N PARAS', len(paras))
for j,p in enumerate(paras):
    t = p.get('para_type')
    if t == 1:
        txt = p.get('text') or {}
        nodes = txt.get('nodes') or []
        s = ''.join((n.get('word') or {}).get('words','') if n.get('type')=='TEXT' else f"<{n.get('type')}:{(n.get('rich') or {}).get('text','')}>" for n in nodes)
        print(f'[{j}] T1: {s}')
        for n in nodes:
            if n.get('type') != 'TEXT':
                print('     RICH', json.dumps(n, ensure_ascii=False)[:400])
    elif t == 2:
        pic = p.get('pic') or {}
        print(f'[{j}] PIC: {pic.get("url")}  w={pic.get("width")} h={pic.get("height")} size={pic.get("size")}')
    else:
        print(f'[{j}] type={t}: {json.dumps(p, ensure_ascii=False)[:300]}')
