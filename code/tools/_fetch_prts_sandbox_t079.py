# -*- coding: utf-8 -*-
"""T-079: 抓 PRTS 作战机制/sandbox wikitext。必须带 User-Agent + Accept。"""
import os, sys, urllib.parse, urllib.request, ssl

OUT = r"C:\Users\23922\Documents\ds_harness\ak\_raw\prts\作战机制_sandbox.wikitext.txt"
TITLE = "作战机制/sandbox"
URL = "https://prts.wiki/index.php?title=%s&action=raw" % urllib.parse.quote(TITLE, safe="")
HDRS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/122.0 Safari/537.36 AK-KB-Research/1.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

def via_curl_cffi():
    from curl_cffi import requests as cr
    r = cr.get(URL, headers=HDRS, impersonate="chrome", timeout=60, verify=False)
    return r.status_code, r.text

def via_urllib():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(URL, headers=HDRS)
    with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
        return resp.status, resp.read().decode("utf-8", "replace")

def main():
    print("URL:", URL)
    text = None
    try:
        code, text = via_curl_cffi()
        print("curl_cffi status:", code, "len:", len(text))
    except Exception as e:
        print("curl_cffi FAILED:", type(e).__name__, e)
        try:
            code, text = via_urllib()
            print("urllib status:", code, "len:", len(text))
        except Exception as e2:
            print("urllib FAILED:", type(e2).__name__, e2)
            return 2
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print("WROTE:", OUT, len(text), "chars")
    print("HEAD 400:", repr(text[:400]))
    return 0

if __name__ == "__main__":
    sys.exit(main())
