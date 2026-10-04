# -*- coding: utf-8 -*-
"""批量抓取 B 站 UP 主全部专栏并转为 Markdown（Delta JSON 解析）。
用法: python bili_articles.py <mid> <输出目录>
"""
import sys, os, re, time, json
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


def api(url, params, referer, retries=4):
    s = get_s()
    for i in range(retries):
        try:
            r = s.get(url, params=params, timeout=30,
                      headers={"Referer": referer, "Accept": "application/json, text/plain, */*"})
            d = r.json()
            if d.get("code") in (0,):
                return d
            if d.get("code") in (-352, -412):
                time.sleep(10 * (i + 1))
                continue
            return d
        except Exception:
            time.sleep(5 * (i + 1))
    return {"code": -1, "message": "retries exhausted"}


def delta_to_md(content_json):
    """B 站专栏 content Delta JSON -> Markdown 文本。"""
    try:
        ops = json.loads(content_json).get("ops", [])
    except Exception:
        return content_json or ""
    out = []
    for op in ops:
        ins = op.get("insert")
        attr = op.get("attributes") or {}
        if isinstance(ins, str):
            if attr.get("header"):
                lvl = int(attr["header"])
                out.append("\n" + "#" * lvl + " " + ins.strip() + "\n")
            elif attr.get("blockquote"):
                out.append("> " + ins + "\n")
            elif attr.get("code-block"):
                out.append("```\n" + ins + "\n```\n")
            elif attr.get("list"):
                out.append("- " + ins.strip() + "\n")
            else:
                out.append(ins)
        elif isinstance(ins, dict):
            if "image" in ins:
                out.append(f"\n![img]({ins['image']})\n")
            elif "link" in ins:
                out.append(f"[{ins.get('text','链接')}]({ins['link']})")
    return re.sub(r"\n{3,}", "\n\n", "".join(out))


def main():
    mid, outdir = sys.argv[1], sys.argv[2]
    os.makedirs(outdir, exist_ok=True)
    # 1. 专栏列表
    arts = []
    pn = 1
    while True:
        d = api("https://api.bilibili.com/x/space/article",
                {"mid": mid, "pn": pn, "ps": 30},
                f"https://space.bilibili.com/{mid}/article")
        if d.get("code") != 0:
            print("list error:", d)
            break
        al = d["data"].get("articles") or []
        arts.extend(al)
        if len(al) < 30:
            break
        pn += 1
        time.sleep(3)
    print(f"# {mid}: {len(arts)} articles")
    for a in arts:
        aid = a["id"]
        title = a["title"].replace("/", "_").replace("\\", "_").replace(":", "：").strip()
        path = os.path.join(outdir, f"{aid}_{title}.md")
        if os.path.exists(path):
            print(f"  SKIP {aid} {title}")
            continue
        vd = api("https://api.bilibili.com/x/article/view", {"id": aid},
                 f"https://www.bilibili.com/read/cv{aid}")
        if vd.get("code") != 0:
            print(f"  view err {aid}: {vd.get('message')}")
            continue
        dd = vd["data"]
        md = delta_to_md(dd.get("content") or "")
        ts = dd.get("publish_time", 0)
        import datetime
        datestr = datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d") if ts else ""
        head = (f"# {title}\n\n"
                f"> UP：{dd.get('author_name', '')} | 发布：{datestr} | 阅读：{dd.get('read_count', '')}\n"
                f"> 原文：https://www.bilibili.com/read/cv{aid}\n\n---\n\n")
        with open(path, "w", encoding="utf-8") as f:
            f.write(head + md)
        print(f"  OK {aid} {title} ({len(md)} chars)")
        time.sleep(4)


if __name__ == "__main__":
    main()
