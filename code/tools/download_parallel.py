# download_parallel.py — 6 线程并行 1MB 分块下载（raw.githubusercontent 单连接易断）
# 用法: python download_parallel.py <url> <输出路径> <总大小>
import os, subprocess, time, sys
from concurrent.futures import ThreadPoolExecutor, as_completed

URL = sys.argv[1] if len(sys.argv) > 1 else "https://raw.githubusercontent.com/Kengxxiao/ArknightsGameData/master/zh_CN/gamedata/battle/buff_template_data.json"
FINAL = sys.argv[2] if len(sys.argv) > 2 else r"C:\Users\23922\Documents\ds_harness\ak\_raw\gamedata\buff_template_data.json"
TOTAL = int(sys.argv[3]) if len(sys.argv) > 3 else 27090165
CHUNK = 1048576
DIR = os.path.join(os.path.dirname(FINAL), "parts_" + os.path.basename(FINAL))
os.makedirs(DIR, exist_ok=True)
N = (TOTAL + CHUNK - 1) // CHUNK


def fetch(i):
    start = i * CHUNK
    end = min(start + CHUNK - 1, TOTAL - 1)
    full = end - start + 1
    out = os.path.join(DIR, f"part.{i:04d}")
    saved = os.path.getsize(out) if os.path.exists(out) else 0
    if saved >= full:
        return i, True
    for _ in range(15):
        rstart = start + saved
        if rstart > end:
            break
        tmp = out + ".tmp"
        subprocess.run(["curl.exe", "-s", "--max-time", "150", "-r", f"{rstart}-{end}", URL, "-o", tmp],
                       capture_output=True)
        if os.path.exists(tmp) and os.path.getsize(tmp) > 0:
            with open(out, "ab") as f, open(tmp, "rb") as g:
                f.write(g.read())
            saved = os.path.getsize(out)
            os.remove(tmp)
        else:
            time.sleep(1)
    return i, saved >= full


def main():
    done = 0
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(fetch, i): i for i in range(N)}
        for f in as_completed(futs):
            i, ok = f.result()
            if ok:
                done += 1
            print(f"chunk {i:02d}: {'OK' if ok else 'FAIL'}", flush=True)
    print(f"chunks done: {done}/{N}")
    with open(FINAL, "wb") as out:
        for i in range(N):
            p = os.path.join(DIR, f"part.{i:04d}")
            if os.path.exists(p):
                with open(p, "rb") as f:
                    out.write(f.read())
    print("FINAL SIZE:", os.path.getsize(FINAL), "target:", TOTAL)


if __name__ == "__main__":
    main()
