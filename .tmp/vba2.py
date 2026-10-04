import zipfile, re, os
src = r"C:\Users\23922\Documents\ds_harness\ak\.tmp\prts_plan_snapshot.xlsm"
if not os.path.exists(src):
    # 从既有 .tmp 快照或 prts+ 目录找
    cands = [p for p in os.listdir(r"C:\Users\23922\Documents\ds_harness\ak\.tmp") if p.endswith(".xlsm")]
    print("cands:", cands); src = os.path.join(r"C:\Users\23922\Documents\ds_harness\ak\.tmp", cands[0])
z = zipfile.ZipFile(src)
vba = z.read("xl/vbaProject.bin")
print("vbaProject.bin size:", len(vba))
out = []
# 1) 可打印 ASCII 串（含单元格引用、命令行、属性名）
for m in re.finditer(rb"[\x20-\x7e]{4,}", vba):
    out.append(m.group().decode("ascii"))
open(r"C:\Users\23922\Documents\ds_harness\ak\.tmp\vba_ascii.txt","w",encoding="utf-8").write("\n".join(out))
print("ascii strings:", len(out))
# 2) 找单元格引用样式
cells = sorted({s for s in out if re.fullmatch(r"[A-Z]{1,2}\d{1,5}", s)})
print("cell-like tokens:", cells[:80])
# 3) 找命令行相关
for s in out:
    if any(k in s for k in ("WScript", "--xlsm", "--debug", "--autoenter", "prts", ".exe", "Shell")):
        print("CMD>", s)
