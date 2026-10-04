# -*- coding: utf-8 -*-
"""批量抓取 PRTS 页面 wikitext（MediaWiki API）。
用法: python fetch_pages.py pages.txt outdir
pages.txt 每行一个页面名。
"""
import sys, os, re, json, time
import urllib.request, urllib.parse

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
API = "https://prts.wiki/api.php"


def fetch(title, retries=3):
    params = urllib.parse.urlencode({
        "action": "parse", "page": title, "prop": "wikitext",
        "format": "json", "formatversion": "2"})
    url = API + "?" + params
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA,
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9"})
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            if i == retries - 1:
                raise
            time.sleep(2 * (i + 1))


def main():
    pagefile, outdir = sys.argv[1], sys.argv[2]
    os.makedirs(outdir, exist_ok=True)
    with open(pagefile, encoding="utf-8") as f:
        pages = [ln.strip() for ln in f if ln.strip()]
    for p in pages:
        safe = re.sub(r'[\\/:*?"<>|]', "_", p)
        try:
            d = fetch(p)
            if "parse" in d and "wikitext" in d["parse"]:
                wt = d["parse"]["wikitext"]
                path = os.path.join(outdir, safe + ".wikitext.txt")
                with open(path, "w", encoding="utf-8") as f:
                    f.write(wt)
                print(f"OK   {p}\tchars={len(wt)}\tredirect={d['parse'].get('redirect','')}")
            elif "error" in d:
                print(f"ERR  {p}\t{d['error'].get('code')}\t{d['error'].get('info')}")
            else:
                print(f"???  {p}\tkeys={list(d.keys())}")
        except Exception as e:
            print(f"EXC  {p}\t{e}")
        time.sleep(0.4)


if __name__ == "__main__":
    main()
