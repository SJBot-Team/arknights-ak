# -*- coding: utf-8 -*-
"""批量转写已下载的 B 站音频（faster-whisper，hf-mirror）。
用法: python bili_transcribe.py <model: small|medium> [--all]
"""
import sys, os, glob
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

AUDIO_DIR = r"E:\__file\ak_kb\downloads\bilibili_audio"
TXT_DIR = r"C:\Users\23922\Documents\ds_harness\ak\_raw\bilibili\transcripts"

# 优先转写的视频（机制教学）
PRIORITY = ["BV1CZ8t6wEyr", "BV14y8269EbS", "BV14gby6LEni", "BV1wPuG6aEyY", "BV1jd3m68E6f"]


def transcribe(path, model_size):
    # ctranslate2 需要 cublas64_12.dll：进程启动后立即注入 PATH（torch 自带 CUDA 运行时）
    torch_lib = r"C:\Users\23922\Documents\ds_harness\课设\comp_physics\.venv\Lib\site-packages\torch\lib"
    if os.path.isdir(torch_lib) and torch_lib not in os.environ.get("PATH", ""):
        os.environ["PATH"] = torch_lib + os.pathsep + os.environ.get("PATH", "")
    os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
    from faster_whisper import WhisperModel
    # 本地模型目录（已手动下载）
    model_dir = r"E:\__file\ak_kb\downloads\whisper_models\faster-whisper-small"
    model = WhisperModel(model_dir, device="cuda", compute_type="float16")
    segments, info = model.transcribe(path, language="zh", vad_filter=True)
    lines = []
    for seg in segments:
        lines.append(f"[{seg.start:7.1f}-{seg.end:7.1f}] {seg.text}")
    base = os.path.basename(path).split(".")[0]
    out = os.path.join(TXT_DIR, base + f"_{model_size}.txt")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return out


def main():
    model_size = sys.argv[1] if len(sys.argv) > 1 else "small"
    do_all = len(sys.argv) > 2 and sys.argv[2] == "--all"
    os.makedirs(TXT_DIR, exist_ok=True)
    files = []
    for bv in PRIORITY:
        p = os.path.join(AUDIO_DIR, bv + ".m4s")
        if os.path.exists(p):
            files.append(p)
    if do_all:
        files = sorted(glob.glob(os.path.join(AUDIO_DIR, "*.m4s")))
    for p in files:
        base = os.path.basename(p).split(".")[0]
        out = os.path.join(TXT_DIR, base + f"_{model_size}.txt")
        if os.path.exists(out):
            print(f"SKIP {base} (已转写)")
            continue
        print(f"# transcribing {base} ...")
        try:
            o = transcribe(p, model_size)
            print(f"  OK -> {o}")
        except Exception as e:
            print(f"  ERR {base}: {str(e)[:150]}")


if __name__ == "__main__":
    main()
