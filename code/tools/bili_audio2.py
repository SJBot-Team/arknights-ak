# -*- coding: utf-8 -*-
"""curl_cffi 直连 B 站下载音频（绕过 yt-dlp 412）。
流程: view 接口拿 cid -> playurl 拿音频流 -> 下载 m4s -> (可选) faster-whisper 转写。
用法: python bili_audio2.py <bvid> [--transcribe]
"""
import sys, os, time, json
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from curl_cffi import requests

AUDIO_DIR = r"E:\__file\ak_kb\downloads\bilibili_audio"
TXT_DIR = r"C:\Users\23922\Documents\ds_harness\ak\_raw\bilibili\transcripts"

_s = None


def get_s():
    global _s
    if _s is None:
        _s = requests.Session(impersonate="chrome")
        _s.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": "https://www.bilibili.com"})
        _s.get("https://www.bilibili.com/", timeout=20)
    return _s


def view(bvid):
    s = get_s()
    d = s.get("https://api.bilibili.com/x/web-interface/view",
              params={"bvid": bvid}, timeout=30).json()
    if d.get("code") != 0:
        return None, d
    v = d["data"]
    return v, None


def playurl(bvid, cid):
    s = get_s()
    d = s.get("https://api.bilibili.com/x/player/playurl",
              params={"bvid": bvid, "cid": cid, "fnval": 16, "fourk": 1},
              timeout=30).json()
    if d.get("code") != 0:
        return None, d
    dash = d["data"].get("dash") or {}
    audios = dash.get("audio") or []
    return audios, None


def download(bvid, url, outpath):
    s = get_s()
    # 流下载
    r = s.get(url, timeout=600, stream=True,
              headers={"Referer": "https://www.bilibili.com", "Origin": "https://www.bilibili.com",
                       "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"})
    with open(outpath, "wb") as f:
        for chunk in r.iter_content(chunk_size=1 << 20):
            f.write(chunk)
    return outpath


def transcribe(path, model_size="small"):
    from faster_whisper import WhisperModel
    os.makedirs(TXT_DIR, exist_ok=True)
    os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
    model_dir = r"E:\__file\ak_kb\downloads\whisper_models\faster-whisper-small"
    model = WhisperModel(model_dir, device="cuda", compute_type="float16")
    segments, info = model.transcribe(path, language="zh", vad_filter=True)
    lines = [f"[{seg.start:7.1f}-{seg.end:7.1f}] {seg.text}" for seg in segments]
    base = os.path.basename(path).split(".")[0]
    out = os.path.join(TXT_DIR, base + ".txt")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return out


def main():
    bvid = sys.argv[1]
    do_ts = len(sys.argv) > 2 and sys.argv[2] == "--transcribe"
    v, err = view(bvid)
    if not v:
        print(f"view ERR: {err}")
        sys.exit(1)
    print(f"title: {v.get('title')} | duration: {v.get('duration')}s | cid: {v.get('cid')} | owner: {v.get('owner',{}).get('name')} | date: {v.get('pubdate')}")
    audios, err = playurl(bvid, v["cid"])
    if not audios:
        print(f"playurl ERR: {err}")
        sys.exit(1)
    # 选音质最高的非 302 流
    a = max(audios, key=lambda x: x.get("bandwidth", 0))
    url = a.get("baseUrl") or a.get("base_url")
    print(f"audio: {a.get('codecs')} bw={a.get('bandwidth')} -> {url[:100]}")
    outpath = os.path.join(AUDIO_DIR, f"{bvid}.m4s")
    download(bvid, url, outpath)
    print(f"saved: {outpath} ({os.path.getsize(outpath)//1024} KB)")
    if do_ts:
        print("transcribing ...")
        txt = transcribe(outpath)
        print(f"transcript: {txt}")


if __name__ == "__main__":
    main()
