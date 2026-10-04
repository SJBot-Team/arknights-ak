# -*- coding: utf-8 -*-
"""测试 wbi keys 获取途径（nav 未登录是否仍返回 wbi_img）。"""
import sys, json, re, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from curl_cffi import requests
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
s = requests.Session(impersonate="chrome")
s.headers.update({"User-Agent": UA, "Referer": "https://www.bilibili.com",
                  "Accept-Language": "zh-CN,zh;q=0.9"})
s.get("https://www.bilibili.com/", timeout=25)
r = s.get("https://api.bilibili.com/x/web-interface/nav", timeout=25,
          headers={"Referer": "https://www.bilibili.com"})
print("nav status", r.status_code)
try:
    d = r.json()
    print("nav code", d.get("code"), "msg", d.get("message"))
    print("has data", bool(d.get("data")), "has wbi", bool((d.get("data") or {}).get("wbi_img")))
    print("keys:", json.dumps((d.get("data") or {}).get("wbi_img"), ensure_ascii=False)[:200])
except Exception as e:
    print("nav parse fail", e, r.text[:200])

# 备用：从首页 HTML 里抠 wbi 图名
time.sleep(2)
h = s.get("https://www.bilibili.com/", timeout=25).text
m = re.findall(r'wbi_img[^}]{0,200}', h)
print("html wbi hits:", len(m), m[:1])
m2 = re.findall(r'/([0-9a-f]{32})\.(?:png|jpg)', h)
print("html 32-hex hits:", m2[:5])
open(r"C:\Users\23922\Documents\ds_harness\ak\_raw\bilibili\_wbi_test.txt", "w",
     encoding="utf-8").write(json.dumps({"nav_code": d.get("code") if 'd' in dir() else None}, ensure_ascii=False))
