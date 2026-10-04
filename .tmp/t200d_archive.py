import json, os, sys, re, html
sys.stdout.reconfigure(encoding='utf-8')
OUT = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'
DST = r'C:\Users\23922\Documents\ds_harness\ak\_raw\bilibili\神祇读神奇\cv53229679_答疑课1_梓兰大嘴花出怪帧三帧索敌.md'

view = json.load(open(os.path.join(OUT, 't200d_view_53229679.json'), encoding='utf-8'))['data']
st = json.loads(open(os.path.join(OUT, 't200d_initial_state.json'), encoding='utf-8').read())
paras = st['detail']['modules'][3]['module_content']['paragraphs']

def runs(nodes):
    out = []
    for n in nodes or []:
        t = n.get('type')
        if t == 'TEXT_NODE_TYPE_WORD':
            w = (n.get('word') or {})
            s = w.get('words') or ''
            style = (w.get('style') or {})
            if style.get('bold') and s.strip():
                s = f'**{s}**'
            out.append(s)
        elif t == 'TEXT_NODE_TYPE_RICH':
            r = n.get('rich') or {}
            txt = r.get('text') or ''
            jurl = r.get('jump_url') or ''
            rtype = (r.get('type') or '').replace('RICH_TEXT_NODE_TYPE_', '')
            out.append(f'[{txt}]({jurl})' if jurl else txt)
        else:
            out.append('')
    return ''.join(out)

lines = []
body = []
nchar = 0
img_i = 0
img_list = []

for p in paras:
    pt = p.get('para_type')
    if pt == 8:
        h = p.get('heading') or {}
        lvl = h.get('level', 2)
        txt = runs(h.get('nodes')).strip()
        if txt:
            body.append(f'{"#" * min(lvl + 1, 5)} {txt}')
    elif pt == 1:
        txt = runs((p.get('text') or {}).get('nodes'))
        if txt.strip() == '':
            continue
        nchar += len(txt.strip())
        body.append(txt.strip())
    elif pt == 2:
        pics = ((p.get('pic') or {}).get('pics')) or []
        for pic in pics:
            img_i += 1
            u = (pic.get('url') or '').replace('http://', 'https://')
            cap = (pic.get('comment') or '').strip()
            img_list.append((img_i, cap, u))
            body.append(f'![图{img_i}{"：" + cap if cap else ""}]({u})')

HDR = f"""# 【神奇答疑课#1】梓兰、大嘴花、出怪帧与三帧索敌

> **原始资料层（③存档）**　抓取日期：2026-09-29　任务：**T-200d**
> 来源：B 站专栏 **cv53229679**　|　UP「神祇读神奇」（mid **374873950**）
> 发布：**2026-09-29**（`publish_time=1790668352`；`ctime/mtime=1790668942`）
> 正文 URL：https://www.bilibili.com/read/cv53229679
> 接口：`https://api.bilibili.com/x/article/view?id=53229679`（`code=0`）+ 页面 `__INITIAL_STATE__`（补图片与标题层级）
> 抓取：`urllib.request`（带 `User-Agent` + `Referer: https://space.bilibili.com/374873950/article`）；**未下载图片**（仅保留链接）
> 字数：`words=2455`；正文纯文本约 **{nchar}** 字；正文图片 **{img_i}** 张
> 数据源引用视频：`BV17qaG6EEHX`（「求大佬解释一下，梓兰再部署为什么不会被大嘴花吃的原理」）
> 分类：生活 / 日常　|　互动：view 1801 / like 118 / favorite 16 / coin 13（抓取时快照）
> ⚠️ 本文为**社区作者结论（T2）**，未经代码核验；学习条目见 `knowledge/03_外部学习/30_神奇答疑课1_梓兰与大嘴花_出怪帧与三帧索敌_20260929.md`

---

"""

lines.append(HDR)
lines.append('\n\n'.join(body))
lines.append('\n\n---\n\n## 附：正文图片清单（仅链接，未下载）\n')
lines.append('| # | 图注（原文 comment） | 链接 |')
lines.append('|---|---|---|')
for i, cap, u in img_list:
    lines.append(f'| {i} | {cap or "（无图注）"} | {u} |')
lines.append('')
lines.append('## 附：抓取元数据\n')
lines.append('```json')
lines.append(json.dumps({
    'id': view.get('id'), 'title': view.get('title'),
    'publish_time': view.get('publish_time'), 'ctime': view.get('ctime'), 'mtime': view.get('mtime'),
    'words': view.get('words'), 'author': {'name': (view.get('author') or {}).get('name'), 'mid': (view.get('author') or {}).get('mid')},
    'stats': view.get('stats'), 'banner_url': view.get('banner_url'),
    'categories': view.get('categories'), 'keywords': view.get('keywords'),
    'plain_text_chars': nchar, 'image_count': img_i,
}, ensure_ascii=False, indent=1))
lines.append('```')
lines.append('')

os.makedirs(os.path.dirname(DST), exist_ok=True)
open(DST, 'w', encoding='utf-8').write('\n'.join(lines))
print('WROTE', DST, os.path.getsize(DST), 'bytes; plain chars', nchar, 'images', img_i)
