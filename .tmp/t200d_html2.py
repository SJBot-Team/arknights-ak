import json, os, sys, re
sys.stdout.reconfigure(encoding='utf-8')
OUT = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'
h = open(os.path.join(OUT,'t200d_html_cv53229679.html'), encoding='utf-8').read()
print('img tags in html:', h.count('<img'))
for mm in re.finditer(r'<img[^>]*>', h):
    print('IMG>', mm.group(0)[:250])
print('--- bfs/article urls ---')
for u in set(re.findall(r'https://[^"\'\\ ]*bfs/article[^"\'\\ ]*', h)):
    print(u)
print('--- all hdslb urls ---')
for u in sorted(set(re.findall(r'https://[a-z0-9.]*hdslb\.com/[^"\'\\ )]+', h))):
    print(u)
print('--- state keys ---')
s = open(os.path.join(OUT,'t200d_initial_state.json'), encoding='utf-8').read()
try:
    st = json.loads(s)
    print(list(st.keys()))
    for k,v in st.items():
        if isinstance(v, dict):
            print(k, '->', list(v.keys())[:20])
        else:
            print(k, '=', str(v)[:120])
except Exception as e:
    print('fail', e)
    print(s[:500])
