# -*- coding: utf-8 -*-
import sys, json, time, datetime
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
p = r"C:\Users\23922\Documents\ds_harness\ak\_raw\bilibili\recent_probe.json"
j = json.load(open(p, encoding="utf-8"))
print("probe_time:", j["probe_time"])

def d(ts):
    return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")

print("\n=== mid 374873950 (神祇读神奇) 投稿列表 ===")
for pg in j["mid_374873950"]:
    print("code=", pg.get("code"), "count=", pg.get("count"), "msg=", pg.get("message"))
    for v in pg.get("videos", [])[:30]:
        print(f'{v["bvid"]} | {d(v["created"])} | {v["length"]:>8} | play={v["play"]} | {v["title"]}')

for key in ("search_user_lapis", "search_user_shenqi", "search_video_1", "search_video_2"):
    s = j.get(key) or {}
    print(f"\n=== {key} === code={s.get('code')} num={s.get('data',{}).get('numResults') if s.get('data') else None}")
    res = ((s.get("data") or {}).get("result")) or []
    for it in res[:25]:
        if "uname" in it:
            print(f'  mid={it.get("mid")} {it.get("uname")} fans={it.get("fans")} sign={it.get("usign")}')
        elif "bvid" in it:
            print(f'  {it.get("bvid")} | {d(it.get("senddate",0))} | {it.get("duration")} | {it.get("author")}(mid={it.get("mid")}) | {it.get("title")}')
        else:
            print("  ", json.dumps(it, ensure_ascii=False)[:200])
