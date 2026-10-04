# -*- coding: utf-8 -*-
"""完整提取 uoep-data.xlsb 全部 sheet 为 CSV（知识库数据源）。"""
import csv, os, sys

SRC = r"E:\__file\舟数据\通用\uoep-data (3).xlsb"
OUTDIR = r"C:\Users\23922\Documents\ds_harness\ak\data\operators"


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    import pyxlsb
    with pyxlsb.open_workbook(SRC) as wb:
        print("sheets:", wb.sheets)
        for sn in wb.sheets:
            rows = []
            with wb.get_sheet(sn) as ws:
                for row in ws.rows():
                    rows.append(["" if c.v is None else c.v for c in row])
            out = os.path.join(OUTDIR, f"uoep_{sn}.csv")
            with open(out, "w", encoding="utf-8-sig", newline="") as f:
                w = csv.writer(f)
                w.writerows(rows)
            print(f"OK {sn}: {len(rows)} rows -> {out}")


if __name__ == "__main__":
    main()
