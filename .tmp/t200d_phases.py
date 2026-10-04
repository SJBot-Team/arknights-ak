import json, os, sys
sys.stdout.reconfigure(encoding='utf-8')
GD = r'C:\Users\23922\Documents\ds_harness\ak\_raw\gamedata'
ct = json.load(open(os.path.join(GD,'character_table.json'), encoding='utf-8'))
c = ct['char_1048_orchd2']
print('### char_1048_orchd2 phases ###')
for ph in c.get('phases') or []:
    print(' phase', ph.get('characterPrefabKey'), ph.get('rangeId'), 'maxLvl', ph.get('maxLevel'))
    print('   trait:', json.dumps(ph.get('trait'), ensure_ascii=False)[:800])
print('### full top-level keys with content ###')
for k,v in c.items():
    if v not in (None, [], {}, ''):
        s = json.dumps(v, ensure_ascii=False)
        if k in ('name','rarity','profession','subProfessionId','tagList','nationId','groupId','teamId','displayNumber','appellation','itemUsage','itemDesc'):
            print(f'  {k} = {s[:200]}')
print()
print('### operators whose trait/talent text mentions 隐匿 ###')
for cid, op in ct.items():
    txt = json.dumps({'trait': op.get('trait'), 'talents': op.get('talents'),
                      'phases_trait': [p.get('trait') for p in (op.get('phases') or [])]}, ensure_ascii=False)
    if '隐匿' in txt:
        print(' ', cid, op.get('name'))
print()
print('### subProfession of char_1048_orchd2 / trait desc search ###')
s = open(os.path.join(GD,'character_table.json'), encoding='utf-8').read()
i = s.find('"char_1048_orchd2"')
print(s[i:i+400])
