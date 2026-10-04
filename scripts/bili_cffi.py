# -*- coding: utf-8 -*-
"""B 站抓取（curl_cffi 浏览器指纹 + wbi 签名 + 动态 cookie）。
用法: python bili_cffi.py <mid> info|videos|articles [pn]
"""
import sys, time, hashlib, json
from curl_cffi import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

mixinKeyEncTab = [46,47,18,2,53,8,23,32,15,50,10,31,58,3,45,35,27,43,5,49,33,9,42,19,29,28,14,39,12,38,41,13,37,48,7,16,24,55,40,61,26,17,0,1,60,51,30,4,22,25,54,21,56,59,6,63,57,62,11,36,20,34,44,52]

_session = None


def get_session():
    global _session
    if _session is None:
        s = requests.Session(impersonate="chrome")
        s.headers.update({"User-Agent": UA, "Referer": "https://www.bilibili.com",
                          "Accept-Language": "zh-CN,zh;q=0.9"})
        s.get("https://www.bilibili.com/", timeout=20)  # 拿 buvid3/b_nut 等
        _session = s
    return _session


def api_get(url, params=None, referer="https://www.bilibili.com"):
    s = get_session()
    r = s.get(url, params=params, timeout=30,
              headers={"Referer": referer, "Accept": "application/json, text/plain, */*"})
    return r.json()


def get_wbi_keys():
    d = api_get("https://api.bilibili.com/x/web-interface/nav")
    img = d["data"]["wbi_img"]["img_url"].split("/")[-1].split(".")[0]
    sub = d["data"]["wbi_img"]["sub_url"].split("/")[-1].split(".")[0]
    return img, sub


def enc_wbi(params, img_key, sub_key):
    mixin_key = "".join((img_key + sub_key)[i] for i in mixinKeyEncTab)[:32]
    p = dict(params)
    p["wts"] = round(time.time())
    p = dict(sorted(p.items()))
    p = {k: "".join(ch for ch in str(v) if ch not in "!'()*") for k, v in p.items()}
    import urllib.parse
    p["w_rid"] = hashlib.md5((urllib.parse.urlencode(p) + mixin_key).encode()).hexdigest()
    return p


def user_info(mid):
    img, sub = get_wbi_keys()
    p = enc_wbi({"mid": mid}, img, sub)
    d = api_get("https://api.bilibili.com/x/space/wbi/acc/info", p,
                referer=f"https://space.bilibili.com/{mid}")
    if d.get("code") != 0:
        return d
    u = d["data"]
    return {"name": u.get("name"), "sign": u.get("sign"), "level": u.get("level"),
            "official": u.get("official"), "fans": u.get("follower")}


def videos(mid, pn=1, ps=30):
    img, sub = get_wbi_keys()
    p = enc_wbi({"mid": mid, "pn": pn, "ps": ps, "order": "pubdate"}, img, sub)
    d = api_get("https://api.bilibili.com/x/space/wbi/arc/search", p,
                referer=f"https://space.bilibili.com/{mid}/video")
    if d.get("code") != 0:
        return d
    page = d["data"]["page"]
    vlist = d["data"]["list"]["vlist"]
    out = [{"bvid": v["bvid"], "title": v["title"], "created": v["created"],
            "length": v["length"], "play": v["play"], "comment": v.get("comment")} for v in vlist]
    return {"count": page.get("count"), "page": pn, "videos": out}


def articles(mid, pn=1, ps=30):
    # 已验证接口：x/space/article（无需 wbi 签名）
    d = api_get("https://api.bilibili.com/x/space/article",
                {"mid": mid, "pn": pn, "ps": ps},
                referer=f"https://space.bilibili.com/{mid}/article")
    if d.get("code") != 0:
        return d
    al = d["data"].get("articles") or []
    out = [{"id": a.get("id"), "title": a.get("title"), "publish_time": a.get("publish_time"),
            "view": (a.get("stats") or {}).get("view"), "words": a.get("words")} for a in al]
    return {"count": d["data"].get("count"), "articles": out}


def main():
    mid = sys.argv[1]
    mode = sys.argv[2] if len(sys.argv) > 2 else "info"
    pn = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    if mode == "info":
        print(json.dumps(user_info(mid), ensure_ascii=False, indent=1))
    elif mode == "videos":
        d = videos(mid, pn)
        print(json.dumps(d, ensure_ascii=False, indent=1))
    elif mode == "articles":
        d = articles(mid, pn)
        print(json.dumps(d, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
