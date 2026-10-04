# -*- coding: utf-8 -*-
"""查看 probe_0928.json 的 search 结果里 mid=592610 / 标题含神祇 的全部条目。"""
import json, sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
P = r"C:\Users\23922\Documents\ds_harness\ak\_raw\bilibili\probe_0928.json"
d = json.load(open(P, encoding="utf-8"))
print("=== searches ===")
for kw, sr in d.get("searches", {}).items():
    if sr.get("code") != 0:
        print(f"[{kw}] code={sr.get('code')}")
        continue
    print(f"[{kw}] numResults={sr.get('numResults')} n={len(sr['results'])}")
    for v in sr["results"]:
        if v.get("mid") == 592610 or "神祇" in (v.get("title") or ""):
            ts = time.strftime("%Y-%m-%d", time.localtime(v.get("pubdate") or 0))
            print(f"   {v['bvid']} {ts} {v.get('author')}({v.get('mid')}) | {v['title'][:70]}")
print("=== space pages ===")
for r in d.get("lapis_space", []):
    print(f"pn={r.get('page')} code={r.get('code')} count={r.get('count')} n={len(r.get('videos') or [])}")
    for v in (r.get("videos") or []):
        if "神祇" in v["title"]:
            ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(v["created"]))
            print(f"   {v['bvid']} {ts} {v['length']} {v['title'][:70]}")
print("=== views (parts) ===")
for v in d.get("views", []):
    if v.get("code") != 0:
        continue
    if "神祇" not in (v.get("title") or ""):
        continue
    print(f"{v['bvid']} {v['title']} pub={time.strftime('%Y-%m-%d', time.localtime(v['pubdate']))} "
          f"parts={len(v['pages'])} total={v['total_parts_dur']}s")
    for p in v["pages"]:
        print(f"    P{p['page']} {p['duration']}s {p['part']}")
