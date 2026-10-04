# -*- coding: utf-8 -*-
import sys, json, datetime
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
p = r"C:\Users\23922\Documents\ds_harness\ak\_raw\bilibili\lapis_probe.json"
j = json.load(open(p, encoding="utf-8"))
print("probe_time:", j["probe_time"])
def d(ts):
    return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
for i, pg in enumerate(j.get("lapis_pages") or []):
    print(f"\n=== Lapis___ pn={pg.get('page')} code={pg.get('code')} count={pg.get('count')} msg={pg.get('message')} ===")
    for v in pg.get("videos", []):
        print(f'{v["bvid"]} | {d(v["created"])} | {v["length"]:>8} | play={v["play"]} | {v["title"]}')
kw = j.get("lapis_kw_jizhi") or {}
print(f"\n=== Lapis___ keyword=机制 code={kw.get('code')} count={kw.get('count')} ===")
for v in kw.get("videos", [])[:30]:
    print(f'{v["bvid"]} | {d(v["created"])} | {v["length"]:>8} | {v["title"]}')
for key in ("search_录播", "search_神祇读神奇"):
    s = j.get(key) or {}
    print(f"\n=== {key} code={s.get('code')} ===")
    for it in ((s.get("data") or {}).get("result") or [])[:30]:
        t = (it.get("title") or "").replace('<em class="keyword">', "").replace("</em>", "")
        print(f'  {it.get("bvid")} | {d(it.get("senddate",0))} | {it.get("duration")} | {it.get("author")}(mid={it.get("mid")}) | {t}')
