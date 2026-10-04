# -*- coding: utf-8 -*-
"""T-067 探测：Lapis___(mid 592610) 与「神祇读神奇」09-21~09-28 新投稿。
用法: python bili_probe_0928.py
输出: JSON 落盘 ak/_raw/bilibili/probe_0928.json + stdout 摘要
策略: 每页独立退避重试(15/30/45s)；兜底 search/type 按 mid 过滤。
"""
import sys, os, time, json, hashlib, urllib.parse

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from curl_cffi import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
MIXIN = [46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49, 33, 9,
         42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1,
         60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36, 20, 34, 44, 52]
OUT = r"C:\Users\23922\Documents\ds_harness\ak\_raw\bilibili\probe_0928.json"
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


def api(url, params=None, referer="https://www.bilibili.com", tries=4, backoffs=(15, 30, 45),
        ok=(-101,)):
    """通用请求：失败按 backoffs 退避重试。ok 里的 code 视为"可用返回"不重试。
    注意 nav 未登录返回 -101 但 data.wbi_img 存在，必须放行。"""
    last = None
    for i in range(tries):
        try:
            r = s().get(url, params=params, timeout=35,
                        headers={"Referer": referer,
                                 "Accept": "application/json, text/plain, */*"})
            d = r.json()
        except Exception as e:
            last = {"code": "EXC", "message": str(e)[:150]}
            time.sleep(6 + 6 * i)
            continue
        if d.get("code") == 0 or d.get("code") in ok:
            time.sleep(3)
            return d
        last = d
        bo = backoffs[min(i, len(backoffs) - 1)]
        print(f"  ! code={d.get('code')} {url.split('/')[-1]} -> backoff {bo}s", flush=True)
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


def space_page(mid, pn, img, sub):
    p = enc({"mid": mid, "pn": pn, "ps": 30, "order": "pubdate", "tid": 0, "keyword": ""},
            img, sub)
    d = api("https://api.bilibili.com/x/space/wbi/arc/search", p,
            referer=f"https://space.bilibili.com/{mid}/video", tries=4)
    if d.get("code") != 0:
        return {"code": d.get("code"), "page": pn, "message": str(d.get("message"))[:80]}
    pg = d["data"].get("page", {})
    return {"code": 0, "page": pn, "count": pg.get("count"), "videos": [
        {"bvid": v["bvid"], "title": v["title"], "created": v["created"],
         "length": v["length"], "play": v["play"], "comment": v.get("comment")}
        for v in d["data"]["list"]["vlist"]]}


def search_video(kw, page=1):
    d = api("https://api.bilibili.com/x/web-interface/search/type",
            {"search_type": "video", "keyword": kw, "page": page, "page_size": 50},
            referer="https://search.bilibili.com/", tries=3)
    if d.get("code") != 0:
        return {"code": d.get("code"), "kw": kw, "page": page}
    res = []
    for v in (d["data"].get("result") or []):
        res.append({"bvid": v.get("bvid"), "title": (v.get("title") or "").replace(
            '<em class="keyword">', "").replace("</em>", ""),
            "author": v.get("author"), "mid": v.get("mid"),
            "pubdate": v.get("pubdate"), "duration": v.get("duration"),
            "typename": v.get("typename")})
    return {"code": 0, "kw": kw, "page": page, "numResults": d["data"].get("numResults"),
            "results": res}


def view(bvid):
    d = api("https://api.bilibili.com/x/web-interface/view", {"bvid": bvid}, tries=3)
    if d.get("code") != 0:
        return {"bvid": bvid, "code": d.get("code")}
    dd = d["data"]
    pages = dd.get("pages") or []
    # 分P 标题里的起录时间可帮助判断是否同一场连续分段
    return {"bvid": bvid, "code": 0, "title": dd.get("title"),
            "owner": dd.get("owner", {}).get("name"), "mid": dd.get("owner", {}).get("mid"),
            "pubdate": dd.get("pubdate"), "duration": dd.get("duration"),
            "desc": (dd.get("desc") or "")[:400],
            "pages": [{"page": p["page"], "cid": p["cid"], "part": p["part"],
                       "duration": p["duration"]} for p in pages],
            "total_parts_dur": sum(p["duration"] for p in pages)}


def main():
    t0 = time.time()
    out = {"probe_time": time.strftime("%Y-%m-%d %H:%M:%S"),
           "target_window": "2026-09-21 ~ 2026-09-28"}
    img, sub = wbi_keys()
    out["lapis_space"] = []
    for pn in (1, 2, 3):
        print(f"[space] mid={MID} pn={pn}", flush=True)
        r = space_page(MID, pn, img, sub)
        out["lapis_space"].append(r)
        if r.get("code") == 0:
            for v in r["videos"]:
                ds = time.strftime("%Y-%m-%d %H:%M", time.localtime(v["created"]))
                print(f"   {v['bvid']} {ds} {v['length']:>8} {v['title'][:60]}", flush=True)
        # 分页之间也停一下，降低 -412
        time.sleep(8)

    out["searches"] = {}
    for kw in ["神祇读神奇", "【神祇读神奇】", "神祇读神奇 机制", "Lapis___ 神祇"]:
        print(f"[search] {kw}", flush=True)
        out["searches"][kw] = search_video(kw, 1)
        time.sleep(8)

    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"saved {OUT}  ({time.time()-t0:.0f}s)", flush=True)

    # 候选：窗口内 + mid/Lapis 或标题含神祇
    cands = {}

    def add(bv, title, created, author="", mid=None, length="", src=""):
        if bv not in cands:
            cands[bv] = {"bvid": bv, "title": title, "created": created, "author": author,
                         "mid": mid, "length": length, "src": src}

    for r in out["lapis_space"]:
        if r.get("code") != 0:
            continue
        for v in r["videos"]:
            if v["created"] >= time.mktime(time.strptime("2026-09-18", "%Y-%m-%d")):
                add(v["bvid"], v["title"], v["created"], "Lapis___", MID, v["length"], "space")
    for kw, sr in out["searches"].items():
        if sr.get("code") != 0:
            continue
        for v in sr["results"]:
            pd = v.get("pubdate") or 0
            if pd >= time.mktime(time.strptime("2026-09-18", "%Y-%m-%d")) and (
                    v.get("mid") == MID or "神祇" in (v.get("title") or "")):
                add(v["bvid"], v["title"], pd, v.get("author"), v.get("mid"),
                    str(v.get("duration")), "search:" + kw)

    out["candidates"] = sorted(cands.values(), key=lambda x: -x["created"])
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n=== candidates (>= 2026-09-18) ===")
    for c in out["candidates"]:
        ds = time.strftime("%Y-%m-%d %H:%M", time.localtime(c["created"]))
        print(f"  {c['bvid']} {ds} {c['author']}({c['mid']}) {c['length']} {c['title'][:70]}")

    # 对窗口内候选取 view（分P）
    out["views"] = []
    for c in out["candidates"]:
        if c["created"] < time.mktime(time.strptime("2026-09-21", "%Y-%m-%d")):
            continue
        print(f"[view] {c['bvid']}", flush=True)
        v = view(c["bvid"])
        out["views"].append(v)
        json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        if v.get("code") == 0:
            print(f"   pub={time.strftime('%Y-%m-%d', time.localtime(v['pubdate']))} "
                  f"parts={len(v['pages'])} total={v['total_parts_dur']}s "
                  f"| {v['title'][:60]}")
            for p in v["pages"]:
                print(f"      P{p['page']} {p['duration']:>6}s  {p['part'][:60]}")
        time.sleep(6)

    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\nDONE {time.time()-t0:.0f}s -> {OUT}")


if __name__ == "__main__":
    main()
