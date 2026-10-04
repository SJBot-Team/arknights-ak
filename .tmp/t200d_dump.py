import json, os, sys, re
sys.stdout.reconfigure(encoding='utf-8')
OUT = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'
d = json.load(open(os.path.join(OUT, 't200d_view_53229679.json'), encoding='utf-8'))
dd = d['data']
c = dd['content']
print('=== RAW CONTENT FULL (repr, tags visible) ===')
print(repr(c))
print()
print('=== origin_image_urls ===')
for u in dd.get('origin_image_urls') or []:
    print(u)
print('=== content_pic_list ===')
print(json.dumps(dd.get('content_pic_list'), ensure_ascii=False, indent=1))
print('=== list (index) ===')
print(json.dumps(dd.get('list'), ensure_ascii=False)[:2000])
print('=== keywords ===', dd.get('keywords'))
print('=== media ===', json.dumps(dd.get('media'), ensure_ascii=False)[:500])
print('=== template_id ===', dd.get('template_id'), 'category', json.dumps(dd.get('categories'), ensure_ascii=False))
