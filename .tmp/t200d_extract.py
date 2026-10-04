import json, os, sys, re, html
sys.stdout.reconfigure(encoding='utf-8')
OUT = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'
d = json.load(open(os.path.join(OUT, 't200d_view_53229679.json'), encoding='utf-8'))
dd = d['data']
print('keys:', list(dd.keys()))
print('TITLE:', dd.get('title'))
print('PUBTIME:', dd.get('publish_time'), dd.get('ctime'), dd.get('mtime'))
print('AUTHOR:', dd.get('author', {}).get('name'), dd.get('author', {}).get('mid'))
print('words:', dd.get('words'), 'content len:', len(dd.get('content') or ''))
print('image_urls:', dd.get('image_urls'))
print('summary:', dd.get('summary'))
print('stats:', dd.get('stats'))
c = dd.get('content') or ''
open(os.path.join(OUT, 't200d_content_raw.html'), 'w', encoding='utf-8').write(c)
print('=== RAW CONTENT (first 6000) ===')
print(c[:6000])
