import json, sys, os, re
sys.stdout.reconfigure(encoding='utf-8')
GD = r'C:\Users\23922\Documents\ds_harness\ak\_raw\gamedata'
bt = json.load(open(os.path.join(GD,'buff_template_data.json'), encoding='utf-8'))
keys = [k for k in bt.keys() if 'orchd2' in k]
print('orchd2 buff keys:', keys)
for k in keys:
    s = json.dumps(bt[k], ensure_ascii=False)
    print('='*70)
    print(k, 'len', len(s))
    print(s[:2200])
