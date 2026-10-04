import json, os, sys, glob
sys.stdout.reconfigure(encoding='utf-8')
GD = r'C:\Users\23922\Documents\ds_harness\ak\_raw\gamedata'
ue = json.load(open(os.path.join(GD,'uniequip_table.json'), encoding='utf-8'))
print('top keys', list(ue.keys()))
ed = ue.get('equipDict', {})
for k in ['uniequip_001_orchd2','uniequip_002_orchd2']:
    v = ed.get(k)
    print('='*70); print(k)
    print(json.dumps(v, ensure_ascii=False, indent=1)[:2500])
print('=== battle_equip table location ===')
for p in glob.glob(r'C:\Users\23922\Documents\ds_harness\ak\**\battle_equip_table.json', recursive=True):
    print(p)
