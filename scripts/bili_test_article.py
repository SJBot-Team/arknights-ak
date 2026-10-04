# -*- coding: utf-8 -*-
import sys, time, json
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from curl_cffi import requests

s = requests.Session(impersonate="chrome")
s.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                  "Accept-Language": "zh-CN,zh;q=0.9"})
s.get("https://www.bilibili.com/", timeout=20)


def get(name, url, params=None, referer="https://space.bilibili.com/374873950/article"):
    try:
        r = s.get(url, params=params, timeout=30,
                  headers={"Referer": referer, "Accept": "application/json, text/plain, */*"})
        d = r.json()
        print(f"{name}: code={d.get('code')} msg={d.get('message')}")
        if d.get("data") and isinstance(d["data"], dict):
            print("  data keys:", list(d["data"].keys())[:8])
            for k in ("articles", "list"):
                if k in d["data"]:
                    arr = d["data"][k]
                    print(f"  {k} len:", len(arr) if arr else 0)
                    for a in (arr or [])[:12]:
                        print(f"    {a.get('id')} | {a.get('title')}")
    except Exception as e:
        print(f"{name}: ERR {e}")


get("space article", "https://api.bilibili.com/x/space/article", {"mid": "374873950", "pn": "1", "ps": "30"})
time.sleep(2)
get("upowers/list", "https://api.bilibili.com/x/article/upowers/list", {"mid": "374873950", "pn": "1", "ps": "30"})
