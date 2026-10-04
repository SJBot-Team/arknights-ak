import sys, zipfile
sys.path.insert(0, r"C:\Users\23922\Documents\ds_harness\ak\.tmp")
sys.stdout.reconfigure(encoding="utf-8")
from vba_extract import CFB, ovba_decompress
z = zipfile.ZipFile(r"C:\Users\23922\Documents\ds_harness\ak\.tmp\prts_plan_snapshot.xlsm")
cfb = CFB(z.read("xl/vbaProject.bin"))
print("sect", cfb.sect, "mini", cfb.mini, "cutoff", cfb.cutoff, "fatsects", cfb.n_fat, "miniFATsecs", cfb.n_minifat)
print("ministream len", len(cfb.ministream))
for name, blob in cfb.streams():
    print(f"  {name:24} size={len(blob):7} head={blob[:12].hex()}")
