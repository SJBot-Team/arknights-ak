# -*- coding: utf-8 -*-
"""批量：下载 B 站音频 → faster-whisper 转写（增量写盘，输出 <BV>.txt）。
用法: python bili_recent_batch.py BV1 BV2 BV3
"""
import sys, os, time, glob
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

AUDIO_DIR = r"E:\__file\ak_kb\downloads\bilibili_audio"
TXT_DIR = r"C:\Users\23922\Documents\ds_harness\ak\_raw\bilibili\transcripts"
TORCH_LIB = r"C:\Users\23922\Documents\ds_harness\课设\comp_physics\.venv\Lib\site-packages\torch\lib"
MODEL_DIR = r"E:\__file\ak_kb\downloads\whisper_models\faster-whisper-small"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
_s = None


def s():
    global _s
    if _s is None:
        from curl_cffi import requests
        _s = requests.Session(impersonate="chrome")
        _s.headers.update({"User-Agent": UA, "Referer": "https://www.bilibili.com",
                           "Accept-Language": "zh-CN,zh;q=0.9"})
        _s.get("https://www.bilibili.com/", timeout=25)
    return _s


def download(bvid):
    os.makedirs(AUDIO_DIR, exist_ok=True)
    out = os.path.join(AUDIO_DIR, bvid + ".m4s")
    if os.path.exists(out) and os.path.getsize(out) > 100000:
        print(f"[skip] audio exists {out} ({os.path.getsize(out)//1024} KB)", flush=True)
        return out
    for attempt in range(4):
        try:
            v = s().get("https://api.bilibili.com/x/web-interface/view",
                        params={"bvid": bvid}, timeout=30).json()
            if v.get("code") != 0:
                print(f"[err] view {bvid}: {v.get('code')} {v.get('message')}", flush=True)
                time.sleep(20)
                continue
            d = v["data"]
            print(f"[info] {bvid} | {d['title']} | {d['duration']}s | pub={time.strftime('%Y-%m-%d', time.localtime(d['pubdate']))}", flush=True)
            p = s().get("https://api.bilibili.com/x/player/playurl",
                        params={"bvid": bvid, "cid": d["cid"], "fnval": 16, "fourk": 1},
                        timeout=30).json()
            if p.get("code") != 0:
                print(f"[err] playurl {bvid}: {p.get('code')} {p.get('message')}", flush=True)
                time.sleep(25); continue
            audios = (p["data"].get("dash") or {}).get("audio") or []
            if not audios:
                print(f"[err] no audio stream {bvid}", flush=True); time.sleep(20); continue
            a = max(audios, key=lambda x: x.get("bandwidth", 0))
            url = a.get("baseUrl") or a.get("base_url")
            r = s().get(url, timeout=1200, stream=True,
                        headers={"Referer": "https://www.bilibili.com",
                                 "Origin": "https://www.bilibili.com", "User-Agent": UA})
            tmp = out + ".part"
            n = 0
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 20):
                    f.write(chunk)
                    n += len(chunk)
            os.replace(tmp, out)
            print(f"[ok] {out} ({n//1024//1024} MB)", flush=True)
            time.sleep(6)
            return out
        except Exception as e:
            print(f"[exc] {bvid} attempt {attempt}: {str(e)[:150]}", flush=True)
            time.sleep(15 + 15 * attempt)
    return None


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
        f.write(f"# {bvid}  (faster-whisper small, vad_filter=True, lang=zh)\n")
        for seg in segments:
            f.write(f"[{seg.start:8.1f}-{seg.end:8.1f}] {seg.text.strip()}\n")
            n += 1
            if n % 25 == 0:
                f.flush()
                os.fsync(f.fileno())
                print(f"  ..{bvid} {n} segs, audio_pos={seg.end:.0f}s, elapsed={time.time()-t0:.0f}s", flush=True)
    os.replace(part, final)
    print(f"[txt] {final} ({n} segs, {time.time()-t0:.0f}s)", flush=True)
    return final


_model = None
if __name__ == "__main__":
    for bv in sys.argv[1:]:
        print(f"===== {bv} =====", flush=True)
        final = os.path.join(TXT_DIR, bv + ".txt")
        if os.path.exists(final) and os.path.getsize(final) > 500:
            print(f"[skip] transcript exists {final}", flush=True)
            continue
        a = download(bv)
        if not a:
            print(f"[FAIL] download {bv}", flush=True); continue
        try:
            transcribe(bv, a)
        except Exception as e:
            print(f"[FAIL] transcribe {bv}: {str(e)[:200]}", flush=True)
