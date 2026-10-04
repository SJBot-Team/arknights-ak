import json, os, sys, re
sys.stdout.reconfigure(encoding='utf-8')
OUT = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'
st = json.loads(open(os.path.join(OUT,'t200d_initial_state.json'), encoding='utf-8').read())
paras = st['detail']['modules'][3]['module_content']['paragraphs']
print(json.dumps(paras[9], ensure_ascii=False, indent=1))
print('=== keys of all paras ===')
for j,p in enumerate(paras):
    print(j, p.get('para_type'), [k for k,v in p.items() if v not in (None, {}, [])])
