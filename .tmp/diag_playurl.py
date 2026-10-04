# -*- coding: utf-8 -*-
"""诊断 playurl：为什么音频流只有 7200s。"""
import sys, json, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from curl_cffi import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
s = requests.Session(impersonate="chrome")
s.headers.update({"User-Agent": UA, "Referer": "https://www.bilibili.com",
                  "Accept-Language": "zh-CN,zh;q=0.9"})
s.get("https://www.bilibili.com/", timeout=25)

BV = "BV1L4ez6oEcc"
v = s.get("https://api.bilibili.com/x/web-interface/view", params={"bvid": BV}, timeout=30).json()
d = v["data"]
print("video duration:", d["duration"], "cid:", d["cid"], "pages:", len(d.get("pages", [])))
for pg in d.get("pages", []):
    print("  page:", pg.get("page"), pg.get("part"), pg.get("duration"), pg.get("cid"))
time.sleep(4)

for label, url, params in [
    ("fnval16", "https://api.bilibili.com/x/player/playurl",
     {"bvid": BV, "cid": d["cid"], "fnval": 16, "fourk": 1}),
    ("fnval16+fnver0", "https://api.bilibili.com/x/player/playurl",
     {"bvid": BV, "cid": d["cid"], "fnval": 16, "fnver": 0, "fourk": 1, "qn": 127}),
    ("fnval4048", "https://api.bilibili.com/x/player/playurl",
     {"bvid": BV, "cid": d["cid"], "fnval": 4048, "fourk": 1}),
]:
    r = s.get(url, params=params, timeout=35,
              headers={"Referer": f"https://www.bilibili.com/video/{BV}",
                       "Accept": "application/json, text/plain, */*"}).json()
    print(f"\n=== {label} code={r.get('code')} msg={r.get('message')} ===")
    if r.get("code") != 0:
        continue
    dd = r["data"]
    print("  keys:", list(dd.keys()))
    dash = dd.get("dash") or {}
    print("  dash.duration:", dash.get("duration"), "minBufferTime:", dash.get("minBufferTime"))
    for i, a in enumerate(dash.get("audio") or []):
        print(f"   audio[{i}] id={a.get('id')} bw={a.get('bandwidth')} codecs={a.get('codecs')} "
              f"mime={a.get('mimeType')} segBase={json.dumps(a.get('SegmentBase'))[:200]}")
        print(f"      url={ (a.get('baseUrl') or '')[:130] }")
    print("  durl:", [(x.get('length'), x.get('size')) for x in (dd.get('durl') or [])])
    time.sleep(6)
