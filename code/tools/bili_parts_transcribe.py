# -*- coding: utf-8 -*-
"""按「分P」下载 B 站音频并转写（解决只取 P1 导致转写只覆盖前 2 小时的问题）。
用法: python bili_parts_transcribe.py BV1 BV2 ...
输出: <TXT_DIR>/<BV>.txt（时间戳为整条 BV 全局时间轴；分P 边界写入头部注释）
"""
import sys, os, time, json, subprocess

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

AK = r"C:\Users\23922\Documents\ds_harness\ak"
AUDIO_DIR = r"E:\__file\ak_kb\downloads\bilibili_audio"
TXT_DIR = r"C:\Users\23922\Documents\ds_harness\ak\_raw\bilibili\transcripts"
TORCH_LIB = r"C:\Users\23922\Documents\ds_harness\课设\comp_physics\.venv\Lib\site-packages\torch\lib"
MODEL_DIR = r"E:\__file\ak_kb\downloads\whisper_models\faster-whisper-small"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
KEEP_AUDIO = os.environ.get("KEEP_AUDIO") == "1"
_s = None
_model = None
_HOTWORDS = None


def s():
    global _s
    if _s is None:
        from curl_cffi import requests
        _s = requests.Session(impersonate="chrome")
        _s.headers.update({"User-Agent": UA, "Referer": "https://www.bilibili.com",
                           "Accept-Language": "zh-CN,zh;q=0.9"})
        _s.get("https://www.bilibili.com/", timeout=25)
    return _s


def api(url, params=None, referer="https://www.bilibili.com", tries=4):
    last = None
    for i in range(tries):
        try:
            d = s().get(url, params=params, timeout=35,
                        headers={"Referer": referer,
                                 "Accept": "application/json, text/plain, */*"}).json()
        except Exception as e:
            last = {"code": "EXC", "message": str(e)[:120]}; time.sleep(8); continue
        if d.get("code") == 0:
            time.sleep(4); return d
        last = d; time.sleep(10 + 10 * i)
    raise RuntimeError(f"{url} -> {last}")


def get_pages(bvid):
    v = api("https://api.bilibili.com/x/web-interface/view", {"bvid": bvid})
    d = v["data"]
    pages = d.get("pages") or [{"cid": d["cid"], "page": 1, "part": d["title"],
                                "duration": d["duration"]}]
    return d, pages


def dl_part(bvid, pg):
    out = os.path.join(AUDIO_DIR, f"{bvid}_p{pg['page']}.m4s")
    if os.path.exists(out) and os.path.getsize(out) > 200000:
        print(f"[skip] {out} ({os.path.getsize(out)//1048576} MB)", flush=True)
        return out
    p = api("https://api.bilibili.com/x/player/playurl",
            {"bvid": bvid, "cid": pg["cid"], "fnval": 16, "fourk": 1},
            referer=f"https://www.bilibili.com/video/{bvid}")
    audios = (p["data"].get("dash") or {}).get("audio") or []
    if not audios:
        raise RuntimeError(f"no audio {bvid} p{pg['page']}")
    a = max(audios, key=lambda x: x.get("bandwidth", 0))
    urls = [a.get("baseUrl") or a.get("base_url")] + (a.get("backupUrl") or a.get("backup_url") or [])
    tmp = out + ".part"
    for attempt in range(3):
        for u in urls:
            try:
                r = s().get(u, timeout=1200, stream=True,
                            headers={"Referer": "https://www.bilibili.com",
                                     "Origin": "https://www.bilibili.com", "User-Agent": UA})
                n = 0
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1 << 20):
                        f.write(chunk); n += len(chunk)
                if n > 200000:
                    os.replace(tmp, out)
                    print(f"[ok] {out} ({n//1048576} MB, expect ~{pg['duration']}s)", flush=True)
                    return out
            except Exception as e:
                print(f"  [dl exc] p{pg['page']} try{attempt}: {str(e)[:100]}", flush=True)
            time.sleep(8)
    raise RuntimeError(f"download failed {bvid} p{pg['page']}")


def hotword_prompt():
    """热词（initial_prompt）：优先读 ak\\.tmp\\hotwords.txt（由 glossary_lookup.py --hotwords 生成）；
    没有该文件时直接调用 glossary_lookup 导出，再退回内置小表。**只放正词**（放误写会强化错误）。"""
    global _HOTWORDS
    if _HOTWORDS is not None:
        return _HOTWORDS
    terms = []
    p = os.path.join(AK, ".tmp", "hotwords.txt")
    try:
        if not os.path.exists(p):
            subprocess.run([sys.executable, os.path.join(AK, "code", "tools", "glossary_lookup.py"),
                            "--hotwords"], stdout=open(p, "w", encoding="utf-8"), timeout=120)
        if os.path.exists(p):
            terms = [l.strip() for l in open(p, encoding="utf-8") if l.strip()]
    except Exception as e:
        print(f"[!] 热词导出失败（忽略）：{e}", flush=True)
    if not terms:
        terms = ["索敌", "阻挡", "阻挡偏移", "避障力", "失衡", "仇恨", "嘲讽", "前摇", "后摇",
                 "晕眩", "隐匿", "部署费用", "技力", "阻挡数", "重量", "抛光"]
    # whisper 的 initial_prompt 是"上下文"，太长会拖慢且易漂移 ⇒ 压到 ~200 词/800 字符
    s = "、".join(dict.fromkeys(terms))
    _HOTWORDS = s[:800]
    print(f"[热词] {len(terms)} 词（截断至 {len(_HOTWORDS)} 字符）", flush=True)
    return _HOTWORDS


def model():
    global _model
    if _model is None:
        if TORCH_LIB not in os.environ.get("PATH", ""):
            os.environ["PATH"] = TORCH_LIB + os.pathsep + os.environ.get("PATH", "")
        os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
        from faster_whisper import WhisperModel
        _model = WhisperModel(MODEL_DIR, device="cuda", compute_type="float16")
    return _model


def run(bvid):
    final = os.path.join(TXT_DIR, bvid + ".txt")
    if os.path.exists(final) and os.path.getsize(final) > 500 and ".part" not in final:
        print(f"[skip] transcript exists {final}", flush=True)
        return
    d, pages = get_pages(bvid)
    print(f"[info] {bvid} | {d['title']} | total={d['duration']}s | parts={len(pages)} | "
          f"pub={time.strftime('%Y-%m-%d', time.localtime(d['pubdate']))}", flush=True)
    os.makedirs(TXT_DIR, exist_ok=True)
    os.makedirs(AUDIO_DIR, exist_ok=True)
    part = final + ".part"
    offset = 0.0
    total_segs = 0
    t0 = time.time()
    with open(part, "w", encoding="utf-8") as f:
        f.write(f"# {bvid} {d['title']}\n")
        f.write(f"# owner={d.get('owner',{}).get('name')} pub={time.strftime('%Y-%m-%d', time.localtime(d['pubdate']))} "
                f"total_duration={d['duration']}s parts={len(pages)}\n")
        f.write(f"# 转写: faster-whisper small / vad_filter=True / lang=zh ; 时间戳=整条 BV 全局时间轴\n")
        cum = 0.0
        for pg in pages:
            f.write(f"# --- P{pg['page']} 「{pg['part']}」 duration={pg['duration']}s global_offset={cum:.1f}s ---\n")
            cum += pg["duration"]
        f.flush(); os.fsync(f.fileno())
        for pg in pages:
            audio = dl_part(bvid, pg)
            m = model()
            # 热词：用名词对照表导出的正词做 initial_prompt，减少"索迪/必占力"这类误写
            # 生成方式：python ak\code\tools\glossary_lookup.py --hotwords > ak\.tmp\hotwords.txt
            segs, info = m.transcribe(audio, language="zh", vad_filter=True,
                                      initial_prompt=hotword_prompt())
            n = 0
            for seg in segs:
                f.write(f"[{seg.start + offset:8.1f}-{seg.end + offset:8.1f}] {seg.text.strip()}\n")
                n += 1; total_segs += 1
                if n % 50 == 0:
                    f.flush(); os.fsync(f.fileno())
                    print(f"  ..p{pg['page']} {n} segs, global_pos={seg.end + offset:.0f}s, "
                          f"elapsed={time.time()-t0:.0f}s", flush=True)
            offset += pg["duration"]
            if not KEEP_AUDIO:
                try:
                    os.remove(audio)
                    print(f"  [clean] removed {os.path.basename(audio)}", flush=True)
                except Exception as e:
                    print(f"  [clean warn] {e}", flush=True)
    os.replace(part, final)
    print(f"[txt] {final} ({total_segs} segs, {time.time()-t0:.0f}s)", flush=True)


if __name__ == "__main__":
    for bv in sys.argv[1:]:
        print(f"===== {bv} =====", flush=True)
        try:
            run(bv)
        except Exception as e:
            print(f"[FAIL] {bv}: {str(e)[:250]}", flush=True)
