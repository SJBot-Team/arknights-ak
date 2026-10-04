# -*- coding: utf-8 -*-
"""从 PRTS 干员页面 wikitext 提取基础属性，输出比对表。"""
import os, re, sys, glob

OP_DIR = r"C:\Users\23922\Documents\ds_harness\ak\_raw\prts\operators"
OUT = r"C:\Users\23922\Documents\ds_harness\ak\_raw\zhoudata\operator_base_stats.txt"


def extract(path):
    with open(path, encoding="utf-8") as f:
        t = f.read()
    d = {"page": os.path.basename(path).replace(".wikitext.txt", "")}

    m = re.search(r"\|干员名=([^\n|]+)", t)
    if m:
        d["name"] = m.group(1).strip()
    m = re.search(r"\|稀有度=(\d+)", t)
    if m:
        d["rarity"] = m.group(1)
    m = re.search(r"\|职业=([^\n|]+)", t)
    if m:
        d["class"] = m.group(1).strip()
    m = re.search(r"\|分支=([^\n|]+)", t)
    if m:
        d["branch"] = m.group(1).strip()
    m = re.search(r"\|位置=([^\n|]+)", t)
    if m:
        d["pos"] = m.group(1).strip()

    # 属性模板
    m = re.search(r"\{\{属性\n(.*?)\n\}\}", t, re.S)
    if m:
        body = m.group(1)
        for key in ("再部署", "部署费用", "阻挡数", "攻击速度"):
            mm = re.search(r"\|" + key + r"=([^\n|]+)", body)
            if mm:
                d[key] = mm.group(1).strip()
        mm = re.search(r"\|精英2_满级_攻击=([\d.]+)", body)
        if mm:
            d["atk90"] = mm.group(1)
        mm = re.search(r"\|精英1_满级_攻击=([\d.]+)", body)
        if mm:
            d["atk80"] = mm.group(1)
    return d


def main():
    rows = []
    for p in sorted(glob.glob(os.path.join(OP_DIR, "*.wikitext.txt"))):
        d = extract(p)
        rows.append(d)
    header = ["page", "name", "rarity", "class", "branch", "pos",
              "部署费用", "再部署", "阻挡数", "攻击速度", "atk90", "atk80"]
    lines = ["\t".join(header)]
    for d in rows:
        lines.append("\t".join(str(d.get(k, "")) for k in header))
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"OK {len(rows)} operators -> {OUT}")


if __name__ == "__main__":
    main()
