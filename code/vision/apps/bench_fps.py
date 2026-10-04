"""性能基准：验证「60 FPS 实时识别」这条硬指标。

三组测试：
1) 纯匹配吞吐：合成画面上做模板匹配，测每秒可匹配次数（识别能力上限）
2) 真实采集：bettercam/mss 抓屏 N 秒，测采集帧率
3) 端到端：抓屏 + 匹配 的合成帧率（带 60 FPS 节拍验证）

用法：
    python apps/bench_fps.py                # 全部
    python apps/bench_fps.py --seconds 3    # 指定时长
    python apps/bench_fps.py --roi 0.05     # 只匹配右下 5% 区域（ROI 越小越快）
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from kernel.vision import find_template  # noqa: E402


def bench_match(reps: int = 300, frame_size=(1920, 1080), tpl_size=(64, 64), scales=None):
    w, h = frame_size
    rng = np.random.default_rng(42)
    frame = (rng.random((h, w, 3)) * 255).astype(np.uint8)
    tpl = frame[400:400 + tpl_size[1], 600:600 + tpl_size[0]].copy()
    # 让模板有点特征，避免纯噪声导致的病态相关
    cv2.rectangle(tpl, (4, 4), (tpl_size[0] - 5, tpl_size[1] - 5), (255, 255, 255), 3)
    cv2.circle(frame, (632, 432), 20, (255, 255, 255), 3)

    t0 = time.perf_counter()
    hits = 0
    for _ in range(reps):
        m = find_template(frame, tpl, threshold=0.7, scales=scales)
        hits += len(m)
    dt = time.perf_counter() - t0
    return {"reps": reps, "hits": hits, "total_sec": dt, "per_sec": reps / dt, "ms_each": dt / reps * 1000}


def bench_roi_match(reps: int = 300, frame_size=(1920, 1080), tpl_size=(64, 64), roi_frac=0.2):
    """只在大图的局部 ROI 中匹配 —— 实战最常用的加速手段。"""
    w, h = frame_size
    rng = np.random.default_rng(7)
    frame = (rng.random((h, w, 3)) * 255).astype(np.uint8)
    x0, y0 = int(w * (1 - roi_frac)), int(h * (1 - roi_frac))
    roi = frame[y0:y0 + 300, x0:x0 + 400].copy()
    cv2.rectangle(roi, (10, 10), (90, 60), (0, 255, 0), 3)
    tpl = roi[10:61, 10:91].copy()

    t0 = time.perf_counter()
    hits = 0
    for _ in range(reps):
        hits += len(find_template(roi, tpl, threshold=0.7))
    dt = time.perf_counter() - t0
    return {"reps": reps, "hits": hits, "roi_px": roi.shape[:2], "total_sec": dt,
            "per_sec": reps / dt, "ms_each": dt / reps * 1000}


def bench_capture(seconds: float = 3.0, backend: str = "bettercam"):
    """真实抓屏帧率（需要可用的桌面会话）。"""
    from kernel.registry import load_plugins
    load_plugins(ROOT / "plugins")
    from kernel.capture import pick_capture

    order = [backend] + [b for b in ("bettercam", "dxcam", "mss") if b != backend]
    cap = pick_capture(order)
    frames = 0
    t0 = time.perf_counter()
    try:
        while time.perf_counter() - t0 < seconds:
            cap.grab()
            frames += 1
    finally:
        cap.close()
    dt = time.perf_counter() - t0
    return {"backend": cap.name, "frames": frames, "seconds": round(dt, 3), "fps": frames / dt}


def bench_e2e(seconds: float = 3.0, target_fps: int = 60, backend: str = "bettercam"):
    """端到端：抓屏 + 模板匹配，验证能否稳定跑满目标帧率。"""
    from kernel import Engine

    engine = Engine({"target_fps": target_fps, "capture": [backend, "dxcam", "mss"]}, root=ROOT, verbose=False)
    engine.open()
    stats = engine.run(seconds=seconds)
    engine.close()
    return stats


def bench_multi_roi(nodes: int = 8, reps: int = 120, roi=(160, 120), tpl_size=(48, 48)):
    """模拟实战：一帧内对 N 个节点各做一次小 ROI 匹配（MAA 式做法）。

    这是判断「能否稳定 60 FPS 做实时识别」的关键指标：
    单帧成本 = N × 单次 ROI 匹配耗时；只要 < 16.7ms 就能 60 FPS。
    """
    rng = np.random.default_rng(11)
    frame = (rng.random((1080, 1920, 3)) * 255).astype(np.uint8)
    rw, rh = roi
    rois, tpls = [], []
    for i in range(nodes):
        x0 = (i * 137) % (1920 - rw)
        y0 = (i * 91) % (1080 - rh)
        sub = frame[y0:y0 + rh, x0:x0 + rw].copy()
        cv2.rectangle(sub, (10, 10), (10 + tpl_size[0], 10 + tpl_size[1]), (0, 255, 0), 2)
        rois.append(sub)
        tpls.append(sub[10:10 + tpl_size[1] + 1, 10:10 + tpl_size[0] + 1].copy())

    t0 = time.perf_counter()
    hits = 0
    for _ in range(reps):
        for sub, tpl in zip(rois, tpls):
            hits += len(find_template(sub, tpl, threshold=0.7))
    dt = time.perf_counter() - t0
    per_frame = dt / reps
    return {"nodes": nodes, "reps": reps, "roi": roi, "tpl": tpl_size, "hits": hits,
            "per_frame_ms": per_frame * 1000, "fps": 1.0 / per_frame,
            "verdict": "✅ 可稳定 60 FPS" if per_frame * 1000 < 16.0 else "⚠️ 超过 16.7ms，需再缩小 ROI 或降采样"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=3.0)
    ap.add_argument("--reps", type=int, default=300)
    ap.add_argument("--backend", default="bettercam")
    ap.add_argument("--skip-capture", action="store_true")
    args = ap.parse_args()

    print("=" * 72)
    print("① 纯模板匹配吞吐（1920x1080 全帧，64x64 模板）")
    r = bench_match(args.reps)
    print(f"   {r['reps']} 次 / {r['total_sec']:.2f}s → {r['per_sec']:.1f} 次/秒（每次 {r['ms_each']:.2f} ms）")

    print("\n② ROI 限定匹配（400x300 区域）—— 实战加速方式")
    r2 = bench_roi_match(args.reps)
    print(f"   {r2['reps']} 次 / {r2['total_sec']:.2f}s → {r2['per_sec']:.1f} 次/秒（每次 {r2['ms_each']:.3f} ms，ROI {r2['roi_px']}）")

    print("\n③ 多尺度匹配（scales=[0.9,1.0,1.1]，相当于 3 倍算力）")
    r3 = bench_match(max(30, args.reps // 5), scales=[0.9, 1.0, 1.1])
    print(f"   {r3['reps']} 次 / {r3['total_sec']:.2f}s → {r3['per_sec']:.1f} 次/秒（每次 {r3['ms_each']:.2f} ms）")

    print("\n④ 多节点 ROI 识别（模拟实战：8 个节点 × 160x120 ROI）—— 60 FPS 的判据")
    r4 = bench_multi_roi()
    print(f"   {r4['nodes']} 节点/帧 → 单帧 {r4['per_frame_ms']:.2f} ms → 理论上限 {r4['fps']:.0f} FPS  {r4['verdict']}")

    if not args.skip_capture:
        print(f"\n⑤ 真实抓屏帧率（{args.backend}，{args.seconds}s）")
        try:
            c = bench_capture(args.seconds, args.backend)
            print(f"   {c['backend']}: {c['frames']} 帧 / {c['seconds']}s → **{c['fps']:.1f} FPS**")
        except Exception as exc:
            print(f"   抓屏测试失败（可能无桌面会话）: {exc!r}")

        print(f"\n⑥ 端到端（抓屏+节拍，目标 60 FPS，{args.seconds}s）")
        try:
            e = bench_e2e(args.seconds, 60, args.backend)
            print(f"   帧数 {e['frames']} / {e['seconds']}s → **{e['loop_fps']} FPS**"
                  f"（抓屏均值 {e['grab_ms_avg']} ms，流水线均值 {e['step_ms_avg']} ms）")
        except Exception as exc:
            print(f"   端到端失败: {exc!r}")

    print("\n结论：④ 是「能否 60 FPS 识别」的判据（单帧 <16.7ms）；①/②/③ 说明搜索范围与尺度的代价。")


if __name__ == "__main__":
    main()
