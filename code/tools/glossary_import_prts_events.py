# -*- coding: utf-8 -*-
"""抓 PRTS「用户:调零修罗/Buff事件列表」并生成 ak\\glossary\\08_PRTS_Buff事件.tsv。

来源与口径：PRTS = 玩家统一口径（**T2**）；本表用于与本地 `05_枚举词典.tsv`（贝娜的量角器，18 条 event.*）交叉校验与补充。
抓取要点（T-075 实测）：PRTS 对无浏览器头请求返回 403 ⇒ 必须带 UA + Accept；用 `action=raw` 取 wikitext 原文。
"""
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
AK = r'C:\Users\23922\Documents\ds_harness\ak'
RAW = os.path.join(AK, '_raw', 'prts', '调零修罗')
OUT = os.path.join(AK, 'glossary', '08_PRTS_Buff事件.tsv')
URL = ('https://prts.wiki/index.php?title=%E7%94%A8%E6%88%B7:%E8%B0%83%E9%9B%B6%E4%BF%AE%E7%BD%97/'
       'Buff%E4%BA%8B%E4%BB%B6%E5%88%97%E8%A1%A8&action=raw')
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9',
    'Referer': 'https://prts.wiki/',
}
HEADER = ['汉语拼音', '官方汉语命名', '代码层ID', '一句话说明', '知识库地址', '玩家俗称', '来源', '对照（本地 05_枚举词典）']


def fetch():
    os.makedirs(RAW, exist_ok=True)
    dst = os.path.join(RAW, 'Buff事件列表.wikitext.txt')
    if os.path.exists(dst) and os.path.getsize(dst) > 500:
        print('已存在原始存档，跳过网络抓取:', dst)
        return open(dst, encoding='utf-8').read()
    text = None
    try:
        from curl_cffi import requests as cq
        r = cq.get(URL, headers=HEADERS, impersonate='chrome', timeout=30)
        if r.status_code == 200:
            text = r.text
    except Exception as e:
        print('curl_cffi 失败:', e)
    if text is None:
        import urllib.request
        req = urllib.request.Request(URL, headers=HEADERS)
        text = urllib.request.urlopen(req, timeout=30).read().decode('utf-8', 'replace')
    open(dst, 'w', encoding='utf-8', newline='\n').write(text)
    print('已保存原始存档:', dst, len(text), 'B')
    return text


def main():
    try:
        text = fetch()
    except Exception as e:
        print('[!] 抓取失败：', e)
        return 1
    rows = []
    # wikitext 表格行形如：| ON_BUFF_START || 当Buff开始时 || 备注
    for line in text.split('\n'):
        if not line.startswith('|'):
            continue
        cells = [c.strip() for c in line.lstrip('|').split('||')]
        if len(cells) < 2:
            continue
        key = re.sub(r'[\[\]{}]', '', cells[0])
        if not re.fullmatch(r'[A-Z][A-Z0-9_]+', key):
            continue
        rows.append(['', cells[1], key, '', '', '', 'PRTS 用户:调零修罗/Buff事件列表（T2）',
                     cells[2] if len(cells) > 2 else ''])
    if not rows:
        print('[!] 未解析到条目；原始文件已存档，需人工看格式')
        return 1
    with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\t'.join(HEADER) + '\n')
        for r in rows:
            f.write('\t'.join(r) + '\n')
    print(f'写出 {os.path.basename(OUT)}: {len(rows)} 条')
    for r in rows[:6]:
        print('  ', r[2], '=', r[1])
    return 0


if __name__ == '__main__':
    sys.exit(main())
