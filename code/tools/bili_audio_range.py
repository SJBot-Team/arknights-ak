# -*- coding: utf-8 -*-
"""B 站音频下载（Range 分块，规避 CDN ~60MB 单连接截断）+ faster-whisper 增量转写。
用法: python bili_audio_range.py BV1 BV2 ...
输出: <AUDIO_DIR>/<BV>.m4s 与 <TXT_DIR>/<BV>.txt
"""
import sys, os, time, json
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

AUDIO_DIR = r"E:\__file\ak_kb\downloads\bilibili_audio"
TXT_DIR = r"C:\Users\23922\Documents\ds_harness\ak\_raw\bilibili\transcripts"
TORCH_LIB = r"C:\Users\23922\Documents\ds_harness\课设\comp_physics\.venv\Lib\site-packages\torch\lib"
MODEL_DIR = r"E:\__file\ak_kb\downloads\whisper_models\faster-whisper-small"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
CHUNK = 8 << 20
_s = None
_model = None


def s():
    global _s
    if _s is None:
        from curl_cffi import requests
        _s = requests.Session(impersonate="chrome")
        _s.headers.update({"User-Agent": UA, "Referer": "https://www.bilibili.com",
                           "Accept-Language": "zh-CN,zh;q=0.9"})
        _s.get("https://www.bilibili.com/", timeout=25)
    return _s


def api(url, params=None, tries=4):
    last = None
    for i in range(tries):
        try:
            d = s().get(url, params=params, timeout=35,
                        headers={"Referer": "https://www.bilibili.com",
                                 "Accept": "application/json, text/plain, */*"}).json()
        except Exception as e:
            last = {"code": "EXC", "message": str(e)[:120]}; time.sleep(8); continue
        if d.get("code") == 0:
            time.sleep(4); return d
        last = d; time.sleep(12 + 12 * i)
    return last


def stream_urls(bvid):
    v = api("https://api.bilibili.com/x/web-interface/view", {"bvid": bvid})
    if v.get("code") != 0:
        raise RuntimeError(f"view {bvid}: {v}")
    d = v["data"]
    p = api("https://api.bilibili.com/x/player/playurl",
            {"bvid": bvid, "cid": d["cid"], "fnval": 16, "fourk": 1})
    if p.get("code") != 0:
        raise RuntimeError(f"playurl {bvid}: {p}")
    audios = (p["data"].get("dash") or {}).get("audio") or []
    if not audios:
        raise RuntimeError(f"no audio {bvid}")
    a = max(audios, key=lambda x: x.get("bandwidth", 0))
    urls = [a.get("baseUrl") or a.get("base_url")] + (a.get("backupUrl") or a.get("backup_url") or [])
    return d, a, urls


def total_size(url):
    r = s().get(url, timeout=60, stream=True,
                headers={"Referer": "https://www.bilibili.com", "Origin": "https://www.bilibili.com",
                         "User-Agent": UA, "Range": "bytes=0-1"})
    cr = r.headers.get("Content-Range") or ""
    r.close()
    if "/" in cr:
        try:
            return int(cr.split("/")[-1])
        except ValueError:
            pass
    cl = r.headers.get("Content-Length")
    return int(cl) if cl and cl.isdigit() else None


def fetch_range(url, start, end, tries=4):
    for i in range(tries):
        try:
            r = s().get(url, timeout=300, stream=True,
                        headers={"Referer": "https://www.bilibili.com",
                                 "Origin": "https://www.bilibili.com", "User-Agent": UA,
                                 "Range": f"bytes={start}-{end}"})
            if r.status_code not in (200, 206):
                r.close(); time.sleep(5 + 5 * i); continue
            buf = r.content
            r.close()
            if buf:
                return buf
        except Exception as e:
            print(f"    [range exc] {start}-{end}: {str(e)[:100]}", flush=True)
        time.sleep(5 + 5 * i)
    return None


def download(bvid):
    os.makedirs(AUDIO_DIR, exist_ok=True)
    out = os.path.join(AUDIO_DIR, bvid + ".m4s")
    meta_p = os.path.join(AUDIO_DIR, bvid + ".meta.json")
    d, a, urls = stream_urls(bvid)
    print(f"[info] {bvid} | {d['title']} | video={d['duration']}s | pub="
          f"{time.strftime('%Y-%m-%d', time.localtime(d['pubdate']))} | bw={a.get('bandwidth')} codecs={a.get('codecs')}", flush=True)
    json.dump({"bvid": bvid, "title": d["title"], "duration": d["duration"],
               "pubdate": d["pubdate"], "owner": d.get("owner", {}).get("name"),
               "bandwidth": a.get("bandwidth"), "codecs": a.get("codecs")},
              open(meta_p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    url = urls[0]
    tot = total_size(url)
    if not tot:
        for u in urls[1:]:
            tot = total_size(u); url = u
            if tot:
                break
    if not tot:
        raise RuntimeError(f"cannot determine size {bvid}")
    print(f"[size] total={tot/1048576:.1f} MB", flush=True)

    if os.path.exists(out) and os.path.getsize(out) == tot:
        print(f"[skip] complete {out}", flush=True)
        return out

    tmp = out + ".part"
    with open(tmp, "wb") as f:
        pos = 0
        while pos < tot:
            end = min(pos + CHUNK, tot) - 1
            buf = fetch_range(url, pos, end)
            if buf is None:
                for u in urls[1:]:
                    buf = fetch_range(u, pos, end)
                    if buf:
                        url = u
                        break
            if buf is None:
                raise RuntimeError(f"chunk failed at {pos} {bvid}")
            f.write(buf)
            pos += len(buf)
            if pos % (CHUNK * 4) < CHUNK:
                print(f"  ..{bvid} {pos/1048576:.1f}/{tot/1048576:.1f} MB", flush=True)
        f.flush(); os.fsync(f.fileno())
    if os.path.getsize(tmp) != tot:
        raise RuntimeError(f"size mismatch {os.path.getsize(tmp)} != {tot}")
    os.replace(tmp, out)
    print(f"[ok] {out} ({tot/1048576:.1f} MB)", flush=True)
    return out


def transcribe(bvid, audio):
    global _model
    if TORCH_LIB not in os.environ.get("PATH", ""):
        os.environ["PATH"] = TORCH_LIB + os.pathsep + os.environ.get("PATH", "")
    os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
    from faster_whisper import WhisperModel
    if _model is None:
        _model = WhisperModel(MODEL_DIR, device="cuda", compute_type="float16")
    os.makedirs(TXT_DIR, exist_ok=True)
    final = os.path.join(TXT_DIR, bvid + ".txt")
    part = final + ".part"
    t0 = time.time()
    segments, info = _model.transcribe(audio, language="zh", vad_filter=True)
    n = 0
    with open(part, "w", encoding="utf-8") as f:
        f.write(f"# {bvid}  faster-whisper small / vad_filter=True / lang=zh\n")
        for seg in segments:
            f.write(f"[{seg.start:8.1f}-{seg.end:8.1f}] {seg.text.strip()}\n")
            n += 1
            if n % 50 == 0:
                f.flush(); os.fsync(f.fileno())
                print(f"  ..{bvid} {n} segs, audio_pos={seg.end:.0f}s, elapsed={time.time()-t0:.0f}s", flush=True)
    os.replace(part, final)
    print(f"[txt] {final} ({n} segs, {time.time()-t0:.0f}s)", flush=True)


if __name__ == "__main__":
    for bv in sys.argv[1:]:
        print(f"===== {bv} =====", flush=True)
        final = os.path.join(TXT_DIR, bv + ".txt")
        if os.path.exists(final) and os.path.getsize(final) > 500:
            print(f"[skip] transcript exists {final}", flush=True); continue
        try:
            a = download(bv)
        except Exception as e:
            print(f"[FAIL] download {bv}: {str(e)[:200]}", flush=True); continue
        try:
            transcribe(bv, a)
        except Exception as e:
            print(f"[FAIL] transcribe {bv}: {str(e)[:200]}", flush=True)
