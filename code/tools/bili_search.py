# -*- coding: utf-8 -*-
"""B 站搜索接口抓取（curl_cffi 浏览器指纹）。
用法: python bili_search.py <search_type: video|article|bili_user> <keyword> [page]
"""
import sys, time, json
from curl_cffi import requests

_s = None


def get_s():
    global _s
    if _s is None:
        _s = requests.Session(impersonate="chrome")
        _s.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Accept-Language": "zh-CN,zh;q=0.9"})
        _s.get("https://www.bilibili.com/", timeout=20)
    return _s


def search(stype, keyword, page=1):
    s = get_s()
    r = s.get("https://api.bilibili.com/x/web-interface/search/type",
              params={"search_type": stype, "keyword": keyword, "page": page, "page_size": 20},
              timeout=30, headers={"Referer": "https://search.bilibili.com/",
                                   "Accept": "application/json, text/plain, */*"})
    d = r.json()
    if d.get("code") != 0:
        return d
    res = d["data"].get("result") or []
    out = []
    for it in res:
        if stype == "video":
            out.append({"bvid": it.get("bvid"), "title": it.get("title"),
                        "author": it.get("author"), "mid": it.get("mid"),
                        "created": it.get("senddate"), "duration": it.get("duration"),
                        "play": it.get("play"), "desc": (it.get("description") or "")[:80]})
        elif stype == "article":
            out.append({"id": it.get("id"), "title": it.get("title"),
                        "author": it.get("author"), "mid": it.get("mid"),
                        "created": it.get("publish_time"), "view": it.get("view"),
                        "desc": (it.get("desc") or "")[:80]})
        elif stype == "bili_user":
            out.append({"mid": it.get("mid"), "uname": it.get("uname"),
                        "fans": it.get("fans"), "sign": (it.get("usign") or "")[:80]})
    return {"numResults": d["data"].get("numResults"), "page": page, "items": out}


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    stype, kw = sys.argv[1], sys.argv[2]
    page = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    d = search(stype, kw, page)
    print(json.dumps(d, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
