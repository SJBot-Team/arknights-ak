# -*- coding: utf-8 -*-
"""下载 B 站视频音频并转写（yt-dlp 仅音频 + faster-whisper）。
用法: python bili_audio.py <bvid> <输出目录> [--transcribe]
"""
import sys, os, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import yt_dlp

AUDIO_DIR = r"E:\__file\ak_kb\downloads\bilibili_audio"
TXT_DIR = r"C:\Users\23922\Documents\ds_harness\ak\_raw\bilibili\transcripts"


def download_audio(bvid, outdir, cookiefile=None):
    os.makedirs(outdir, exist_ok=True)
    opts = {
        "quiet": True, "no_warnings": True,
        "format": "bestaudio/best",
        "outtmpl": os.path.join(outdir, f"{bvid}.%(ext)s"),
        "noplaylist": True,
        "http_headers": {"Referer": "https://www.bilibili.com",
                         "Accept-Language": "zh-CN,zh;q=0.9"},
        "retries": 5, "fragment_retries": 5,
    }
    if cookiefile and os.path.exists(cookiefile):
        opts["cookiefile"] = cookiefile
    url = f"https://www.bilibili.com/video/{bvid}"
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
    fp = ydl.prepare_filename(info)
    if not os.path.exists(fp):
        # 可能下载为 mp4/m4a
        import glob
        cands = glob.glob(os.path.join(outdir, bvid + ".*"))
        fp = cands[0] if cands else None
    return fp, info


def transcribe(path):
    from faster_whisper import WhisperModel
    os.makedirs(TXT_DIR, exist_ok=True)
    # 优先本地模型缓存；CPU/GPU 自动
    model = WhisperModel("small", device="cuda", compute_type="float16",
                         download_root=r"E:\__file\ak_kb\downloads\whisper_models")
    segments, info = model.transcribe(path, language="zh", vad_filter=True)
    lines = []
    for seg in segments:
        lines.append(f"[{seg.start:7.1f}-{seg.end:7.1f}] {seg.text}")
    base = os.path.basename(path).split(".")[0]
    out = os.path.join(TXT_DIR, base + ".txt")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return out


def main():
    bvid = sys.argv[1]
    outdir = sys.argv[2] if len(sys.argv) > 2 else AUDIO_DIR
    do_ts = len(sys.argv) > 3 and sys.argv[3] == "--transcribe"
    cj = os.path.join(os.environ.get("TEMP", "."), "bili_cj2.txt")
    print(f"# downloading {bvid} audio ...")
    fp, info = download_audio(bvid, outdir, cj)
    print(f"  audio: {fp} | {info.get('title')} | duration={info.get('duration')}s")
    if do_ts and fp:
        print("  transcribing ...")
        txt = transcribe(fp)
        print(f"  transcript: {txt}")


if __name__ == "__main__":
    main()
