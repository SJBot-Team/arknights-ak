import json, os, sys, re, time, urllib.request
sys.stdout.reconfigure(encoding='utf-8')
OUT = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'
HDR = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36',
    'Referer': 'https://space.bilibili.com/374873950/article',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9',
}
def get(url, hdr):
    req = urllib.request.Request(url, headers=hdr)
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read().decode('utf-8', 'replace')

h = get('https://www.bilibili.com/read/cv53229679', HDR)
open(os.path.join(OUT,'t200d_html_cv53229679.html'),'w',encoding='utf-8').write(h)
print('html len', len(h))
i = h.find('__INITIAL_STATE__')
print('initial_state idx', i)
m = re.search(r'window\.__INITIAL_STATE__\s*=\s*(.*?);\s*\(function', h, re.S)
if not m:
    m = re.search(r'__INITIAL_STATE__\s*=\s*(\{.*?\});', h, re.S)
if m:
    s = m.group(1)
    open(os.path.join(OUT,'t200d_initial_state.json'),'w',encoding='utf-8').write(s)
    print('state len', len(s))
    try:
        st = json.loads(s)
        def walk(o, path=''):
            if isinstance(o, dict):
                for k,v in o.items():
                    if k in ('content','readInfo','read_info'):
                        print('FOUND', path+'/'+k, type(v))
                    walk(v, path+'/'+k)
            elif isinstance(o, list):
                for n,v in enumerate(o[:5]):
                    walk(v, path+'/'+str(n))
        walk(st)
    except Exception as e:
        print('json parse fail', e)
else:
    print('no initial state')
    print('img count', h.count('<img'))
    for mm in re.finditer(r'<img[^>]*>', h):
        print(mm.group(0)[:200])
