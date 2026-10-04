import json, sys, os, re
sys.stdout.reconfigure(encoding='utf-8')
GD = r'C:\Users\23922\Documents\ds_harness\ak\_raw\gamedata'
st = json.load(open(os.path.join(GD,'skill_table.json'), encoding='utf-8'))
for sid in ['skchr_orchd2_1','skchr_orchd2_2','skchr_orchd2_3']:
    s = st.get(sid)
    if not s: print(sid,'missing'); continue
    print('='*60)
    print(sid, '| levels:', len(s.get('levels') or []))
    lv = (s.get('levels') or [{}])[-1]
    print(' name:', lv.get('name'))
    print(' desc:', lv.get('description'))
    print(' rangeId:', lv.get('rangeId'), 'duration:', lv.get('duration'), 'spData:', json.dumps(lv.get('spData'), ensure_ascii=False))
    print(' blackboard:', json.dumps(lv.get('blackboard'), ensure_ascii=False)[:1500])

print('\n##### battle_equip_table orchd2 #####')
be = json.load(open(os.path.join(GD,'battle_equip_table.json'), encoding='utf-8'))
print([k for k in be.keys() if 'orchd2' in k])
for k,v in be.items():
    if 'orchd2' in k:
        print(k, json.dumps(v, ensure_ascii=False)[:2500])

print('\n##### uniequip_table orchd2 #####')
ue = json.load(open(os.path.join(GD,'uniequip_table.json'), encoding='utf-8'))
ed = ue.get('equipDict', {})
for k in ['uniequip_001_orchd2','uniequip_002_orchd2']:
    v = ed.get(k)
    if v: print(k, json.dumps({kk:vv for kk,vv in v.items() if kk!='itemCost'}, ensure_ascii=False)[:1200])
