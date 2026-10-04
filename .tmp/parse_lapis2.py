# -*- coding: utf-8 -*-
import sys, json, datetime
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
j = json.load(open(r"C:\Users\23922\Documents\ds_harness\ak\_raw\bilibili\lapis_probe2.json", encoding="utf-8"))
print("probe_time:", j["probe_time"])
def d(ts):
    return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
for k in ("lapis_p1", "lapis_p3"):
    pg = j.get(k) or {}
    print(f"\n=== {k} code={pg.get('code')} count={pg.get('count')} msg={pg.get('message')} ===")
    for v in pg.get("videos", []):
        print(f'{v["bvid"]} | {d(v["created"])} | {v["length"]:>8} | play={v["play"]} | {v["title"]}')
seen = {}
for k in ("search_bracket", "search_bracket2", "search_shangke"):
    sr = j.get(k) or {}
    print(f"\n=== {k} code={sr.get('code')} ===")
    for it in ((sr.get("data") or {}).get("result") or []):
        if it.get("mid") != 592610:
            continue
        t = (it.get("title") or "").replace('<em class="keyword">', "").replace("</em>", "")
        seen[it["bvid"]] = (d(it.get("senddate", 0)), it.get("duration"), t)
for bv, (dt, dur, t) in sorted(seen.items(), key=lambda x: x[1][0], reverse=True):
    print(f"  {bv} | {dt} | {dur:>8} | {t}")
