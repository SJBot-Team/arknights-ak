# -*- coding: utf-8 -*-
"""B 站 wbi 签名 API 抓取：UP 主信息 / 视频列表 / 专栏列表。
用法: python bili_wbi.py <mid> [--videos --articles --pn N]
"""
import sys, os, time, hashlib, json, urllib.request, urllib.parse

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
COOKIE = "buvid3=2C1B9BD0-D3F3-09BB-7002-88D57FC7CD7163729infoc; b_nut=1788237463"

mixinKeyEncTab = [46,47,18,2,53,8,23,32,15,50,10,31,58,3,45,35,27,43,5,49,33,9,42,19,29,28,14,39,12,38,41,13,37,48,7,16,24,55,40,61,26,17,0,1,60,51,30,4,22,25,54,21,56,59,6,63,57,62,11,36,20,34,44,52]


def get_mixin_key(orig):
    return "".join(orig[i] for i in mixinKeyEncTab)[:32]


def enc_wbi(params, img_key, sub_key):
    mixin_key = get_mixin_key(img_key + sub_key)
    params = dict(params)
    params["wts"] = round(time.time())
    params = dict(sorted(params.items()))
    params = {k: "".join(ch for ch in str(v) if ch not in "!'()*") for k, v in params.items()}
    query = urllib.parse.urlencode(params)
    params["w_rid"] = hashlib.md5((query + mixin_key).encode()).hexdigest()
    return params


def api_get(url, params=None, referer="https://www.bilibili.com"):
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Referer": referer, "Cookie": COOKIE,
        "Accept": "application/json, text/plain, */*"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def get_wbi_keys():
    d = api_get("https://api.bilibili.com/x/web-interface/nav")
    img = d["data"]["wbi_img"]["img_url"].split("/")[-1].split(".")[0]
    sub = d["data"]["wbi_img"]["sub_url"].split("/")[-1].split(".")[0]
    return img, sub


def get_user_info(mid):
    img, sub = get_wbi_keys()
    p = enc_wbi({"mid": mid}, img, sub)
    d = api_get("https://api.bilibili.com/x/space/wbi/acc/info", p,
                referer=f"https://space.bilibili.com/{mid}")
    if d.get("code") != 0:
        return {"error": d}
    return d["data"]


def get_videos(mid, pn=1, ps=30):
    img, sub = get_wbi_keys()
    p = enc_wbi({"mid": mid, "pn": pn, "ps": ps, "order": "pubdate"}, img, sub)
    d = api_get("https://api.bilibili.com/x/space/wbi/arc/search", p,
                referer=f"https://space.bilibili.com/{mid}/video")
    return d


def get_articles(mid, pn=1, ps=30):
    # 专栏列表（upowers 接口）
    img, sub = get_wbi_keys()
    p = enc_wbi({"mid": mid, "pn": pn, "ps": ps, "sort": "publish_time"}, img, sub)
    d = api_get("https://api.bilibili.com/x/article/upowers/list", p,
                referer=f"https://space.bilibili.com/{mid}/article")
    return d


def main():
    mid = sys.argv[1]
    mode = sys.argv[2] if len(sys.argv) > 2 else "info"
    if mode == "info":
        u = get_user_info(mid)
        print(json.dumps({k: u.get(k) for k in ("name", "sign", "mid", "sex", "level", "official", "vip")}, ensure_ascii=False, indent=1))
    elif mode == "videos":
        d = get_videos(mid)
        print("code:", d.get("code"), d.get("message"))
        if d.get("data"):
            vlist = d["data"].get("list", {}).get("vlist", [])
            print("count:", len(vlist), "total:", d["data"].get("page", {}).get("count"))
            for v in vlist:
                print(f"{v['bvid']} | {v['created']} | {v['length']} | {v['play']} | {v['title']}")
    elif mode == "articles":
        d = get_articles(mid)
        print("code:", d.get("code"), d.get("message"))
        if d.get("data"):
            al = d["data"].get("articles", [])
            print("count:", len(al))
            for a in al:
                print(f"{a.get('id')} | {a.get('publish_time')} | {a.get('title')} | view={a.get('stats',{}).get('view')}")


if __name__ == "__main__":
    main()
