# -*- coding: utf-8 -*-
"""T-067 补漏：Lapis___(592610) 09-21~09-28 神祇投稿确认 + space pn=1/2 重试。
用法: python bili_probe_0928b.py
输出: ak/_raw/bilibili/probe_0928b.json
"""
import sys, os, time, json, hashlib, urllib.parse

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from curl_cffi import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
MIXIN = [46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49, 33, 9,
         42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1,
         60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36, 20, 34, 44, 52]
OUT = r"C:\Users\23922\Documents\ds_harness\ak\_raw\bilibili\probe_0928b.json"
MID = 592610
_s = None


def s():
    global _s
    if _s is None:
        _s = requests.Session(impersonate="chrome")
        _s.headers.update({"User-Agent": UA, "Referer": "https://www.bilibili.com",
                           "Accept-Language": "zh-CN,zh;q=0.9"})
        _s.get("https://www.bilibili.com/", timeout=25)
    return _s


def api(url, params=None, referer="https://www.bilibili.com", tries=5,
        backoffs=(20, 40, 60, 90), ok=(-101,)):
    last = None
    for i in range(tries):
        try:
            r = s().get(url, params=params, timeout=35,
                        headers={"Referer": referer,
                                 "Accept": "application/json, text/plain, */*"})
            d = r.json()
        except Exception as e:
            last = {"code": "EXC", "message": str(e)[:150]}
            time.sleep(8 + 8 * i)
            continue
        if d.get("code") == 0 or d.get("code") in ok:
            time.sleep(4)
            return d
        last = d
        bo = backoffs[min(i, len(backoffs) - 1)]
        print(f"  ! code={d.get('code')} -> backoff {bo}s", flush=True)
        time.sleep(bo)
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


def space_page(mid, pn, img, sub, ps=30):
    p = enc({"mid": mid, "pn": pn, "ps": ps, "order": "pubdate", "tid": 0, "keyword": ""},
            img, sub)
    d = api("https://api.bilibili.com/x/space/wbi/arc/search", p,
            referer=f"https://space.bilibili.com/{mid}/video", tries=5)
    if d.get("code") != 0:
        return {"code": d.get("code"), "page": pn, "message": str(d.get("message"))[:80]}
    pg = d["data"].get("page", {})
    return {"code": 0, "page": pn, "count": pg.get("count"), "videos": [
        {"bvid": v["bvid"], "title": v["title"], "created": v["created"],
         "length": v["length"], "play": v["play"]}
        for v in d["data"]["list"]["vlist"]]}


def search_video(kw, page=1):
    d = api("https://api.bilibili.com/x/web-interface/search/type",
            {"search_type": "video", "keyword": kw, "page": page, "page_size": 50},
            referer="https://search.bilibili.com/", tries=4)
    if d.get("code") != 0:
        return {"code": d.get("code"), "kw": kw, "page": page}
    res = []
    for v in (d["data"].get("result") or []):
        res.append({"bvid": v.get("bvid"),
                    "title": (v.get("title") or "").replace('<em class="keyword">', "")
                             .replace("</em>", ""),
                    "author": v.get("author"), "mid": v.get("mid"),
                    "pubdate": v.get("pubdate"), "duration": v.get("duration")})
    return {"code": 0, "kw": kw, "page": page, "numResults": d["data"].get("numResults"),
            "results": res}


def main():
    t0 = time.time()
    out = {"probe_time": time.strftime("%Y-%m-%d %H:%M:%S")}
    img, sub = wbi_keys()
    out["space_retry"] = []
    for pn in (1, 2):
        print(f"[space retry] pn={pn}", flush=True)
        r = space_page(MID, pn, img, sub)
        out["space_retry"].append(r)
        if r.get("code") == 0:
            for v in r["videos"]:
                ds = time.strftime("%Y-%m-%d %H:%M", time.localtime(v["created"]))
                mark = "  <<< 神祇" if "神祇" in v["title"] else ""
                print(f"   {v['bvid']} {ds} {v['length']:>8} {v['title'][:58]}{mark}",
                      flush=True)
        time.sleep(10)
        json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    # 关键词兜底：只看 mid=592610 或标题含神祇
    out["searches"] = {}
    for kw in ["神祇读神奇", "神祇读神奇 上课回", "上课回 神祇 2026092"]:
        print(f"[search] {kw}", flush=True)
        sr = search_video(kw, 1)
        out["searches"][kw] = sr
        if sr.get("code") == 0:
            for v in sr["results"]:
                if v.get("mid") == MID or "神祇" in (v.get("title") or ""):
                    ds = time.strftime("%Y-%m-%d %H:%M",
                                       time.localtime(v.get("pubdate") or 0))
                    print(f"   {v['bvid']} {ds} {v.get('author')} | {v['title'][:60]}",
                          flush=True)
        time.sleep(10)
        json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"DONE {time.time()-t0:.0f}s -> {OUT}")


if __name__ == "__main__":
    main()
