import json, urllib.request, os, sys, time, re

sys.stdout.reconfigure(encoding='utf-8')

HDR = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36',
    'Referer': 'https://space.bilibili.com/374873950/article',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-CN,zh;q=0.9',
}
OUT = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'

def get(url, hdr=None):
    req = urllib.request.Request(url, headers=hdr or HDR)
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read().decode('utf-8', 'replace')

# retry API with backoff
ok = False
for i in range(6):
    try:
        v = get('https://api.bilibili.com/x/article/view?id=53229679')
        dv = json.loads(v)
        print('try', i, 'code=', dv.get('code'), dv.get('message'))
        if dv.get('code') == 0:
            with open(os.path.join(OUT, 't200d_view_53229679.json'), 'w', encoding='utf-8') as f:
                f.write(v)
            ok = True
            break
    except Exception as e:
        print('try', i, 'EXC', e)
    time.sleep(6 + i * 4)

if not ok:
    # HTML fallback
    print('=== HTML fallback ===')
    h = get('https://www.bilibili.com/read/cv53229679', {
        'User-Agent': HDR['User-Agent'],
        'Referer': 'https://space.bilibili.com/374873950/article',
        'Accept': 'text/html,application/xhtml+xml',
    })
    with open(os.path.join(OUT, 't200d_html_cv53229679.html'), 'w', encoding='utf-8') as f:
        f.write(h)
    print('html len', len(h))
    m = re.search(r'__INITIAL_STATE__\s*=\s*(\{.*?\});\s*\(function', h, re.S)
    if m:
        with open(os.path.join(OUT, 't200d_initial_state.json'), 'w', encoding='utf-8') as f:
            f.write(m.group(1))
        print('initial_state len', len(m.group(1)))
    else:
        print('no __INITIAL_STATE__ match')
        for pat in ['__INITIAL_STATE__', 'readInfo', 'article']:
            print(pat, h.find(pat))
