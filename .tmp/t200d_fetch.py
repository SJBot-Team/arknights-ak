import json, urllib.request, os, sys, io

sys.stdout.reconfigure(encoding='utf-8')

HDR = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36',
    'Referer': 'https://space.bilibili.com/374873950/article',
}

OUT = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'

def get(url):
    req = urllib.request.Request(url, headers=HDR)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode('utf-8', 'replace')

# 1. list
lst = get('https://api.bilibili.com/x/space/article?mid=374873950&pn=1&ps=12&sort=publish_time')
with open(os.path.join(OUT, 't200d_list.json'), 'w', encoding='utf-8') as f:
    f.write(lst)
d = json.loads(lst)
print('LIST code=', d.get('code'))
arts = d.get('data', {}).get('articles') or []
ids = []
for a in arts:
    ids.append(a['id'])
    print(a['id'], a.get('publish_time'), a.get('title', '')[:60])
print('IDS:', ids)
with open(os.path.join(OUT, 't200d_ids.txt'), 'w', encoding='utf-8') as f:
    f.write('\n'.join(str(i) for i in ids))

# 2. view
v = get('https://api.bilibili.com/x/article/view?id=53229679')
with open(os.path.join(OUT, 't200d_view_53229679.json'), 'w', encoding='utf-8') as f:
    f.write(v)
dv = json.loads(v)
print('VIEW code=', dv.get('code'), dv.get('message'))
if dv.get('code') == 0:
    dd = dv['data']
    print('TITLE:', dd.get('title'))
    print('PUBTIME:', dd.get('publish_time'), dd.get('ctime'), dd.get('mtime'))
    print('AUTHOR:', dd.get('author', {}).get('name'), dd.get('author', {}).get('mid'))
    print('WORDS:', dd.get('words'), 'LEN content:', len(dd.get('content') or ''))
    print('IMAGE_URLS:', dd.get('image_urls'))
    print('--- content head 3000 ---')
    print((dd.get('content') or '')[:3000])
