# -*- coding: utf-8 -*-
"""扫描舟数据目录：转存文本类文件为 UTF-8；输出 Excel 结构报告。"""
import os, sys, io

ROOT = r"E:\__file\舟数据"
TEXT_OUT = r"C:\Users\23922\Documents\ds_harness\ak\_raw\zhoudata\text"
REPORT = r"C:\Users\23922\Documents\ds_harness\ak\_raw\zhoudata\scan_report.txt"
EXCEL_SUFFIX = (".xlsx", ".xlsm", ".xlsb")

os.makedirs(TEXT_OUT, exist_ok=True)


def read_any(p):
    with open(p, "rb") as f:
        raw = f.read()
    for enc in ("utf-8-sig", "utf-8", "gbk", "utf-16"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def main():
    lines = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        for fn in sorted(filenames):
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, ROOT)
            ext = os.path.splitext(fn)[1].lower()
            size = os.path.getsize(full)
            if ext in (".txt", ".m"):
                try:
                    text = read_any(full)
                    out = os.path.join(TEXT_OUT, rel.replace(os.sep, "__"))
                    with open(out, "w", encoding="utf-8") as f:
                        f.write(text)
                    lines.append(f"TEXT  {rel}\t{size}B\tchars={len(text)}\t-> {os.path.basename(out)}")
                except Exception as e:
                    lines.append(f"TEXTERR {rel}\t{e}")
            elif ext in EXCEL_SUFFIX:
                try:
                    import openpyxl
                    wb = openpyxl.load_workbook(full, read_only=True, data_only=True)
                    names = wb.sheetnames
                    desc = []
                    for sn in names:
                        ws = wb[sn]
                        # 估算形状
                        try:
                            dim = ws.calculate_dimension()
                            nrows = ws.max_row if ws.max_row else 0
                            ncols = ws.max_column if ws.max_column else 0
                        except Exception:
                            dim, nrows, ncols = "?", 0, 0
                        # 表头候选：前 3 行
                        head = []
                        for r in range(1, min(4, nrows + 1)):
                            row = []
                            for c in range(1, min(ncols, 12) + 1):
                                v = ws.cell(row=r, column=c).value
                                row.append("" if v is None else str(v)[:20])
                            head.append(" | ".join(row))
                        desc.append(f"    sheet[{sn}] rows~{nrows} cols~{ncols} dim={dim}\n      head1: {head[0] if head else ''}\n      head2: {head[1] if len(head)>1 else ''}\n      head3: {head[2] if len(head)>2 else ''}")
                    wb.close()
                    lines.append(f"XLSX  {rel}\t{size}B\n" + "\n".join(desc))
                except ModuleNotFoundError:
                    lines.append(f"XLSX  {rel}\t{size}B\t(openpyxl missing)")
                except Exception as e:
                    lines.append(f"XLSXERR {rel}\t{size}B\t{e}")
            elif ext == ".xlsb":
                lines.append(f"XLSB  {rel}\t{size}B\t(需要 pyxlsb，另行处理)")
            elif ext == ".ggb":
                lines.append(f"GGB   {rel}\t{size}B\t(GeoGebra 压缩包，另行处理)")
            elif ext == ".png":
                lines.append(f"PNG   {rel}\t{size}B")
            else:
                lines.append(f"OTHER {rel}\t{size}B\t{ext}")

    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
