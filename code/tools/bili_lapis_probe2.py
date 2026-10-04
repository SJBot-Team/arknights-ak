# -*- coding: utf-8 -*-
"""补充探测：【神祇读神奇】关键词全量 + Lapis___ 第 1 页重试。"""
import sys, time, json, hashlib, urllib.parse, datetime
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from curl_cffi import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
MIXIN = [46,47,18,2,53,8,23,32,15,50,10,31,58,3,45,35,27,43,5,49,33,9,42,19,29,28,14,39,12,38,41,13,37,48,7,16,24,55,40,61,26,17,0,1,60,51,30,4,22,25,54,21,56,59,6,63,57,62,11,36,20,34,44,52]
OUT = r"C:\Users\23922\Documents\ds_harness\ak\_raw\bilibili\lapis_probe2.json"
_s = None


def s():
    global _s
    if _s is None:
        _s = requests.Session(impersonate="chrome")
        _s.headers.update({"User-Agent": UA, "Referer": "https://www.bilibili.com",
                           "Accept-Language": "zh-CN,zh;q=0.9"})
        _s.get("https://www.bilibili.com/", timeout=25)
    return _s


def api(url, params=None, referer="https://www.bilibili.com", tries=5):
    last = None
    for i in range(tries):
        try:
            r = s().get(url, params=params, timeout=35,
                        headers={"Referer": referer, "Accept": "application/json, text/plain, */*"})
            d = r.json()
        except Exception as e:
            last = {"code": "EXC", "message": str(e)[:120]}
            time.sleep(6 + 6 * i); continue
        if d.get("code") == 0:
            time.sleep(5); return d
        last = d
        time.sleep(15 + 15 * i)
    return last


def wbi_keys():
    d = api("https://api.bilibili.com/x/web-interface/nav")
    img = d["data"]["wbi_img"]["img_url"].split("/")[-1].split(".")[0]
    sub = d["data"]["wbi_img"]["sub_url"].split("/")[-1].split(".")[0]
    return img, sub


def enc(p, img, sub):
    mk = "".join((img + sub)[i] for i in MIXIN)[:32]
    p = dict(p); p["wts"] = round(time.time()); p = dict(sorted(p.items()))
    p = {k: "".join(c for c in str(v) if c not in "!'()*") for k, v in p.items()}
    p["w_rid"] = hashlib.md5((urllib.parse.urlencode(p) + mk).encode()).hexdigest()
    return p


def space_videos(mid, pn, img, sub):
    p = enc({"mid": mid, "pn": pn, "ps": 30, "order": "pubdate", "tid": 0, "keyword": ""}, img, sub)
    d = api("https://api.bilibili.com/x/space/wbi/arc/search", p,
            referer=f"https://space.bilibili.com/{mid}/video")
    if d.get("code") != 0:
        return d
    page = d["data"].get("page", {})
    return {"code": 0, "count": page.get("count"), "page": pn, "videos": [
        {"bvid": v["bvid"], "title": v["title"], "created": v["created"],
         "length": v["length"], "play": v["play"]} for v in d["data"]["list"]["vlist"]]}


def search_video(kw, page=1):
    return api("https://api.bilibili.com/x/web-interface/search/type",
               {"search_type": "video", "keyword": kw, "page": page, "page_size": 50},
               referer="https://search.bilibili.com/")


def main():
    out = {"probe_time": time.strftime("%Y-%m-%d %H:%M:%S")}
    img, sub = wbi_keys()
    out["lapis_p1"] = space_videos(592610, 1, img, sub)
    out["lapis_p3"] = space_videos(592610, 3, img, sub)
    out["search_bracket"] = search_video("【神祇读神奇】")
    time.sleep(5)
    out["search_bracket2"] = search_video("【神祇读神奇】", 2)
    time.sleep(5)
    out["search_shangke"] = search_video("神祇读神奇 上课回")
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("saved", OUT)


if __name__ == "__main__":
    main()
