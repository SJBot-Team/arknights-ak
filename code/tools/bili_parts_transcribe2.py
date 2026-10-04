# -*- coding: utf-8 -*-
"""T-065: 按需补抓「指定分P」的 B 站音频并转写，追加到 <BV>.txt（不覆盖已有 P1 内容）。

与 T-061 的 bili_parts_transcribe.py 的区别：
  1. 只抓 --parts 指定的分P（默认全部分P），已抓过的分P按文件内 `# --- P<N>` 标记跳过（可断点续跑）；
  2. 向 <BV>.txt **追加**，不覆盖；首次创建时把旧的 <BV>_small.txt（旧工具只转了 P1）合并进 P1 段；
  3. 每个分P 下载/转写失败自动退避重试（15/30/45s），仍失败则记录并继续下一个分P，不卡死；
  4. 可选 initial_prompt 注入专有名词热词（ak\\code\\tools\\glossary_lookup.py --hotwords）。

用法:
  python bili_parts_transcribe2.py BV1wPuG6aEyY --parts 2
  python bili_parts_transcribe2.py BV1wPuG6aEyY BV14gby6LEni --parts 2,3
  KEEP_AUDIO=1 环境变量可保留音频；NO_HOTWORDS=1 关闭热词。
输出: <TXT_DIR>/<BV>.txt（时间戳=整条 BV 全局时间轴）
"""
import sys, os, time, subprocess

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bili_parts_transcribe as B  # noqa: E402  复用 api/dl_part/model/get_pages

TXT_DIR = B.TXT_DIR
HOTWORD_TOOL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "glossary_lookup.py")
BACKOFF = (15, 30, 45)
_prompt = None


def hotwords_prompt():
    """从词表工具导出热词，拼成 whisper initial_prompt（失败则返回 None）。"""
    global _prompt
    if _prompt is not None:
        return _prompt or None
    if os.environ.get("NO_HOTWORDS") == "1":
        _prompt = ""
        return None
    try:
        out = subprocess.run([sys.executable, HOTWORD_TOOL, "--hotwords"],
                             capture_output=True, timeout=120)
        words = [w.strip() for w in out.stdout.decode("utf-8", "replace").splitlines()
                 if w.strip() and len(w.strip()) < 20]
        if not words:
            raise RuntimeError("empty hotwords")
        _prompt = "以下是明日方舟机制讨论的专有名词：" + "、".join(words[:80]) + "。"
        print(f"[prompt] {len(words)} hotwords -> initial_prompt", flush=True)
    except Exception as e:
        print(f"[prompt warn] {str(e)[:120]} -> 不使用 initial_prompt", flush=True)
        _prompt = ""
    return _prompt or None


def part_marker(page):
    return f"# --- P{page} "


def head_of(bvid, d, pages):
    cum = 0.0
    lines = [f"# {bvid} {d['title']}",
             f"# owner={d.get('owner', {}).get('name')} pub="
             f"{time.strftime('%Y-%m-%d', time.localtime(d['pubdate']))} "
             f"total_duration={d['duration']}s parts={len(pages)}",
             "# 转写: faster-whisper small / vad_filter=True / lang=zh ; 时间戳=整条 BV 全局时间轴"]
    for pg in pages:
        lines.append(f"# --- P{pg['page']} 「{pg['part']}」 duration={pg['duration']}s "
                     f"global_offset={cum:.1f}s ---")
        cum += pg["duration"]
    return lines


def state_path(bvid):
    return os.path.join(TXT_DIR, bvid + ".parts_state.json")


def load_state(bvid, final):
    """已完成分P 集合：优先读状态文件，其次全文件扫 `# [done] P<n>` 与 P1 合并标记。"""
    import json
    st = {"done": [], "failed": {}}
    if os.path.exists(state_path(bvid)):
        try:
            with open(state_path(bvid), encoding="utf-8") as f:
                st.update(json.load(f))
        except Exception:
            pass
    if os.path.exists(final):
        with open(final, encoding="utf-8", errors="replace") as f:
            for ln in f:
                if ln.startswith("# [done] P"):
                    try:
                        st["done"].append(int(ln.split(" P", 1)[1].split(" ", 1)[0]))
                    except Exception:
                        pass
                if ln.startswith("# [PARTFAIL] P"):
                    try:
                        st["failed"][ln.split(" P", 1)[1].split(" ", 1)[0]] = 1
                    except Exception:
                        pass
    st["done"] = sorted(set(st["done"]))
    return st


def save_state(bvid, st):
    import json
    st["done"] = sorted(set(st["done"]))
    with open(state_path(bvid), "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)


def build_from_old(bvid, pg):
    """把旧 <BV>_small.txt（只覆盖 P1）合并为 P1 段文本行。"""
    old = os.path.join(TXT_DIR, bvid + "_small.txt")
    if not os.path.exists(old):
        return []
    body = []
    with open(old, encoding="utf-8", errors="replace") as f:
        for ln in f:
            ln = ln.rstrip("\n")
            if not ln.strip() or ln.startswith("#"):
                continue
            body.append(ln)
    if not body:
        return []
    print(f"[merge] {os.path.basename(old)} -> P{pg['page']} ({len(body)} 行)", flush=True)
    return [f"# --- P{pg['page']} 「{pg['part']}」 duration={pg['duration']}s "
            f"global_offset=0.0s (旧转写 {bvid}_small.txt 合并, 仅覆盖本分P) ---"] + body


def transcribe_part(bvid, pg, offset, prompt):
    """下载 + 转写单个分P，返回转写行列表；失败抛异常（调用方退避重试）。"""
    audio = B.dl_part(bvid, pg)
    m = B.model()
    kw = {"language": "zh", "vad_filter": True}
    if prompt:
        kw["initial_prompt"] = prompt
    segs, info = m.transcribe(audio, **kw)
    lines = []
    for seg in segs:
        lines.append(f"[{seg.start + offset:8.1f}-{seg.end + offset:8.1f}] {seg.text.strip()}")
    if not B.KEEP_AUDIO:
        try:
            os.remove(audio)
            print(f"  [clean] removed {os.path.basename(audio)}", flush=True)
        except Exception as e:
            print(f"  [clean warn] {e}", flush=True)
    return lines


def run(bvid, want_parts):
    d, pages = B.get_pages(bvid)
    by_page = {pg["page"]: pg for pg in pages}
    if want_parts:
        missing_req = [p for p in want_parts if p not in by_page]
        if missing_req:
            print(f"[warn] {bvid} 请求的分P不存在，已忽略: {missing_req} "
                  f"(实际分P数={len(pages)})", flush=True)
            want_parts = [p for p in want_parts if p in by_page]
    offsets, cum = {}, 0.0
    for pg in pages:
        offsets[pg["page"]] = cum
        cum += pg["duration"]
    print(f"[info] {bvid} | {d['title']} | total={d['duration']}s | parts={len(pages)} | "
          f"pub={time.strftime('%Y-%m-%d', time.localtime(d['pubdate']))}", flush=True)
    os.makedirs(TXT_DIR, exist_ok=True)
    os.makedirs(B.AUDIO_DIR, exist_ok=True)

    final = os.path.join(TXT_DIR, bvid + ".txt")
    if os.path.exists(final) and os.path.getsize(final) > 200:
        st = load_state(bvid, final)
        done = set(st["done"])
        print(f"[resume] {os.path.basename(final)} 已有分P: {sorted(done)}", flush=True)
    else:
        merged = build_from_old(bvid, pages[0])
        with open(final, "w", encoding="utf-8") as f:
            for ln in head_of(bvid, d, pages):
                f.write(ln + "\n")
            for ln in merged:
                f.write(ln + "\n")
            f.flush(); os.fsync(f.fileno())
        st = {"done": [], "failed": {}}
        if merged:  # 旧转写只覆盖 P1
            st["done"].append(pages[0]["page"])
        done = set(st["done"])
        save_state(bvid, st)

    todo = [pg for pg in pages if (not want_parts or pg["page"] in want_parts)
            and pg["page"] not in done]
    if not todo:
        print(f"[skip] {bvid} 所需分P 均已转写", flush=True)
        return
    print(f"[todo] {bvid} 待转写分P: {[pg['page'] for pg in todo]} "
          f"(合计 {sum(pg['duration'] for pg in todo)}s)", flush=True)

    prompt = hotwords_prompt()
    for pg in todo:
        t0 = time.time()
        lines = None
        for attempt, wait in enumerate((0,) + BACKOFF):
            if wait:
                print(f"  [retry] P{pg['page']} 退避 {wait}s (第 {attempt} 次重试)", flush=True)
                time.sleep(wait)
            try:
                lines = transcribe_part(bvid, pg, offsets[pg["page"]], prompt)
                break
            except Exception as e:
                print(f"  [part fail] {bvid} P{pg['page']} attempt{attempt}: {str(e)[:180]}",
                      flush=True)
        if lines is None:
            print(f"[PARTFAIL] {bvid} P{pg['page']} duration={pg['duration']}s "
                  f"offset={offsets[pg['page']]}s", flush=True)
            with open(final, "a", encoding="utf-8") as f:
                f.write(f"# [PARTFAIL] P{pg['page']} 「{pg['part']}」 "
                        f"duration={pg['duration']}s 下载/转写失败\n")
                f.flush(); os.fsync(f.fileno())
            st.setdefault("failed", {})[str(pg["page"])] = int(time.time())
            save_state(bvid, st)
            continue
        with open(final, "a", encoding="utf-8") as f:
            f.write(f"# --- P{pg['page']} 「{pg['part']}」 duration={pg['duration']}s "
                    f"global_offset={offsets[pg['page']]:.1f}s "
                    f"(T-065 补抓 {time.strftime('%Y-%m-%d %H:%M')}) ---\n")
            for ln in lines:
                f.write(ln + "\n")
            f.write(f"# [done] P{pg['page']} segs={len(lines)} "
                    f"elapsed={time.time()-t0:.0f}s\n")
            f.flush(); os.fsync(f.fileno())
        st["done"].append(pg["page"])
        st.setdefault("failed", {}).pop(str(pg["page"]), None)
        save_state(bvid, st)
        print(f"[part ok] {bvid} P{pg['page']} segs={len(lines)} "
              f"offset={offsets[pg['page']]:.0f}s elapsed={time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    argv = [a for a in sys.argv[1:] if not a.startswith("--")]
    parts = None
    for a in sys.argv[1:]:
        if a.startswith("--parts"):
            parts = [int(x) for x in a.split("=", 1)[1].replace(" ", "").split(",") if x]
    for bv in argv:
        print(f"===== {bv} parts={parts or 'ALL'} =====", flush=True)
        try:
            run(bv, parts)
        except Exception as e:
            print(f"[FAIL] {bv}: {str(e)[:300]}", flush=True)
