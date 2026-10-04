import json, sys, os
sys.stdout.reconfigure(encoding='utf-8')
P = r'C:\Users\23922\Documents\ds_harness\ak\_raw\gamedata\character_table.json'
ct = json.load(open(P, encoding='utf-8'))
for cid in ['char_1048_orchd2', 'char_278_orchid']:
    c = ct.get(cid)
    if not c:
        print(cid, 'NOT FOUND'); continue
    print('='*70)
    print(cid, '|', c.get('name'), '|', c.get('rarity'), '|', c.get('profession'), '|', c.get('subProfessionId'))
    print('trait:', json.dumps(c.get('trait'), ensure_ascii=False)[:600])
    print('-- talents --')
    for t in c.get('talents') or []:
        for cand in t.get('candidates') or []:
            print(' unlock', cand.get('unlockCondition'), '|', cand.get('name'), '|', cand.get('description'))
            print('   blackboard:', json.dumps(cand.get('blackboard'), ensure_ascii=False))
    print('-- skills --')
    for s in c.get('skills') or []:
        print(' ', s.get('skillId'), s.get('prefabId'))
    print('-- phases/misc keys --')
    print('  nationId', c.get('nationId'), 'groupId', c.get('groupId'), 'teamId', c.get('teamId'))
    print('  isNotObtainable', c.get('isNotObtainable'), 'tagList', c.get('tagList'))
    print('  canUseGeneralPotentialItem', c.get('canUseGeneralPotentialItem'))
    print('  potentialItemId', c.get('potentialItemId'), 'substitute', c.get('substitute'))
