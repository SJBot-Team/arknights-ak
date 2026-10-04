# -*- coding: utf-8 -*-
"""探测「神祇读神奇」近期新投稿/录播（curl_cffi 指纹 + wbi 签名 + 退避重试）。
用法: python bili_recent_probe.py
输出: JSON 到 stdout，并落盘 ak/_raw/bilibili/recent_probe.json
"""
import sys, os, time, json, hashlib, urllib.parse
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from curl_cffi import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
MIXIN = [46,47,18,2,53,8,23,32,15,50,10,31,58,3,45,35,27,43,5,49,33,9,42,19,29,28,14,39,12,38,41,13,37,48,7,16,24,55,40,61,26,17,0,1,60,51,30,4,22,25,54,21,56,59,6,63,57,62,11,36,20,34,44,52]
OUT = r"C:\Users\23922\Documents\ds_harness\ak\_raw\bilibili\recent_probe.json"

_s = None


def s():
    global _s
    if _s is None:
        _s = requests.Session(impersonate="chrome")
        _s.headers.update({"User-Agent": UA, "Referer": "https://www.bilibili.com",
                           "Accept-Language": "zh-CN,zh;q=0.9"})
        _s.get("https://www.bilibili.com/", timeout=25)
    return _s


def api(url, params=None, referer="https://www.bilibili.com", tries=4):
    last = None
    for i in range(tries):
        try:
            r = s().get(url, params=params, timeout=35,
                        headers={"Referer": referer, "Accept": "application/json, text/plain, */*"})
            d = r.json()
        except Exception as e:  # noqa
            last = {"code": "EXC", "message": str(e)[:120]}
            time.sleep(5 + 5 * i)
            continue
        if d.get("code") == 0:
            time.sleep(4)
            return d
        last = d
        if d.get("code") in (-352, -412, -799):
            time.sleep(8 + 8 * i)
            continue
        time.sleep(4)
        return d
    return last


def wbi_keys():
    d = api("https://api.bilibili.com/x/web-interface/nav")
    img = d["data"]["wbi_img"]["img_url"].split("/")[-1].split(".")[0]
    sub = d["data"]["wbi_img"]["sub_url"].split("/")[-1].split(".")[0]
    return img, sub


def enc(p, img, sub):
    mk = "".join((img + sub)[i] for i in MIXIN)[:32]
    p = dict(p)
    p["wts"] = round(time.time())
    p = dict(sorted(p.items()))
    p = {k: "".join(c for c in str(v) if c not in "!'()*") for k, v in p.items()}
    p["w_rid"] = hashlib.md5((urllib.parse.urlencode(p) + mk).encode()).hexdigest()
    return p


def space_videos(mid, pn=1, img=None, sub=None):
    p = enc({"mid": mid, "pn": pn, "ps": 30, "order": "pubdate", "tid": 0, "keyword": ""}, img, sub)
    d = api("https://api.bilibili.com/x/space/wbi/arc/search", p,
            referer=f"https://space.bilibili.com/{mid}/video")
    if d.get("code") != 0:
        return d
    page = d["data"].get("page", {})
    vl = d["data"]["list"]["vlist"]
    return {"count": page.get("count"), "page": pn, "videos": [
        {"bvid": v["bvid"], "title": v["title"], "created": v["created"],
         "length": v["length"], "play": v["play"], "desc": (v.get("description") or "")[:120]}
        for v in vl]}


def search_type(stype, kw, page=1):
    return api("https://api.bilibili.com/x/web-interface/search/type",
               {"search_type": stype, "keyword": kw, "page": page, "page_size": 30},
               referer="https://search.bilibili.com/")


def main():
    out = {"probe_time": time.strftime("%Y-%m-%d %H:%M:%S")}
    img, sub = wbi_keys()
    out["wbi"] = bool(img and sub)

    # 1) 神祇读神奇 本人投稿
    out["mid_374873950"] = [space_videos(374873950, pn, img, sub) for pn in (1,)]

    # 2) 搜索 UP
    out["search_user_lapis"] = search_type("bili_user", "Lapis")
    out["search_user_shenqi"] = search_type("bili_user", "神祇读神奇")

    # 3) 关键词搜视频
    out["search_video_1"] = search_type("video", "神祇读神奇 机制")
    out["search_video_2"] = search_type("video", "明日方舟 机制 录播 神奇")

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("saved", OUT)


if __name__ == "__main__":
    main()
