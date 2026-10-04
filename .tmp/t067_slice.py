# -*- coding: utf-8 -*-
"""按时间区间切片打印转写（避免通读全文）。
用法: python t067_slice.py <BV> <start_sec> <end_sec> [min_chars]
"""
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
T = r"C:\Users\23922\Documents\ds_harness\ak\_raw\bilibili\transcripts"
LINE = re.compile(r"^\[\s*([0-9.]+)-\s*([0-9.]+)\]\s*(.*)$")


def main():
    bv, a, b = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
    mc = int(sys.argv[4]) if len(sys.argv) > 4 else 0
    with open(f"{T}\\{bv}.txt", encoding="utf-8") as f:
        for ln in f:
            m = LINE.match(ln.strip())
            if not m:
                continue
            s, e, t = float(m.group(1)), float(m.group(2)), m.group(3)
            if s < a or s > b:
                continue
            if len(t) < mc:
                continue
            print(f"[{s:.0f}] {t}")


if __name__ == "__main__":
    main()
