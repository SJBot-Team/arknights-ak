# -*- coding: utf-8 -*-
"""T-065: 复核 5 场 BV 的分P标题/时长/cid（只读 view API）。"""
import sys, json, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BVS = ["BV1wPuG6aEyY", "BV14gby6LEni", "BV14y8269EbS", "BV1CZ8t6wEyr", "BV16xhV6DEF4"]


def main():
    from curl_cffi import requests
    s = requests.Session(impersonate="chrome")
    s.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                                    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                      "Referer": "https://www.bilibili.com"})
    out = {}
    for bv in BVS:
        for i in range(3):
            d = s.get("https://api.bilibili.com/x/web-interface/view",
                      params={"bvid": bv}, timeout=30).json()
            if d.get("code") == 0:
                break
            time.sleep(10 + 10 * i)
        if d.get("code") != 0:
            print(f"[FAIL] {bv} {d.get('code')} {d.get('message')}", flush=True)
            continue
        dd = d["data"]
        rec = {"title": dd["title"], "duration": dd["duration"],
               "pubdate": time.strftime("%Y-%m-%d %H:%M", time.localtime(dd["pubdate"])),
               "owner": dd.get("owner", {}).get("name"), "pages": []}
        for pg in dd.get("pages", []):
            rec["pages"].append({"page": pg["page"], "cid": pg["cid"],
                                 "part": pg["part"], "duration": pg["duration"]})
            print(f"{bv} P{pg['page']:>2} dur={pg['duration']:>6}s cid={pg['cid']:>12} "
                  f"「{pg['part']}」", flush=True)
        print(f"  == {bv} | {dd['title']} | total={dd['duration']}s | pub={rec['pubdate']} | "
              f"up={rec['owner']}", flush=True)
        out[bv] = rec
        time.sleep(4)
    with open(r"C:\Users\23922\Documents\ds_harness\ak\.tmp\t065_pages.json", "w",
              encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
