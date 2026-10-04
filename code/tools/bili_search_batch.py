# -*- coding: utf-8 -*-
"""批量 B 站视频/专栏搜索，结果存 JSON 文件。
用法: python bili_search_batch.py <输出json> <type> <kw1>|<kw2>|...
"""
import sys, json, time, re
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
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
        return {"code": d.get("code"), "message": d.get("message")}
    res = d["data"].get("result") or []
    items = []
    for it in res:
        if stype == "video":
            items.append({"type": "video", "bvid": it.get("bvid"), "title": re.sub(r"<[^>]+>", "", it.get("title") or ""),
                          "author": it.get("author"), "mid": it.get("mid"),
                          "senddate": it.get("senddate"), "duration": it.get("duration"),
                          "play": it.get("play"), "desc": re.sub(r"<[^>]+>", "", (it.get("description") or "")[:100])})
        elif stype == "article":
            items.append({"type": "article", "id": it.get("id"), "title": re.sub(r"<[^>]+>", "", it.get("title") or ""),
                          "author": it.get("author"), "mid": it.get("mid"),
                          "publish_time": it.get("publish_time"), "view": it.get("view"),
                          "desc": re.sub(r"<[^>]+>", "", (it.get("desc") or "")[:100])})
    return {"items": items, "numResults": d["data"].get("numResults")}


def main():
    outfile = sys.argv[1]
    stype = sys.argv[2]
    kws = sys.argv[3].split("|")
    all_items = []
    for kw in kws:
        for page in (1, 2):
            try:
                d = search(stype, kw, page)
            except Exception as e:
                print(f"ERR {kw} p{page}: {e}")
                continue
            items = d.get("items") or []
            print(f"{kw} p{page}: {len(items)} items")
            all_items.extend(items)
            if len(items) < 20:
                break
            time.sleep(2)
        time.sleep(2)
    with open(outfile, "w", encoding="utf-8") as f:
        json.dump(all_items, f, ensure_ascii=False, indent=1)
    print(f"TOTAL {len(all_items)} -> {outfile}")


if __name__ == "__main__":
    main()
