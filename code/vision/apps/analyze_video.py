"""场景② 入口：分析攻略视频，提取操作步骤时间线。

做法：视频文件当帧源（换的只是采集插件），逐帧跑同一套流水线识别，
输出「帧号 / 时间 / 命中标签 / 分数 / 位置 / 触发动作」的时间线 JSON。

用法：
    python apps/analyze_video.py --video "E:\__file\__video\ark.mp4" --pipeline pipelines/demo.json \
        --out "out\timeline.json" --skip 1 --start 0 --end 600
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from kernel import Engine  # noqa: E402
from kernel.registry import TASKS  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True, help="视频文件路径")
    ap.add_argument("--pipeline", required=True, help="流水线 JSON 路径")
    ap.add_argument("--out", default="out/timeline.json", help="时间线输出路径")
    ap.add_argument("--skip", type=int, default=1, help="每 N 帧取 1 帧（1=逐帧，2=隔帧）")
    ap.add_argument("--start", type=float, default=0.0, help="起始秒")
    ap.add_argument("--end", type=float, default=None, help="结束秒")
    ap.add_argument("--min-gap-ms", type=int, default=500, help="同标签最小记录间隔（去抖）")
    args = ap.parse_args()

    cfg = {
        "target_fps": 0,                 # 视频分析不需要节拍，能跑多快跑多快
        "capture": ["video"],
        "capture_kwargs": {"path": args.video, "skip": args.skip,
                           "start_sec": args.start, "end_sec": args.end},
        "input": [],                      # 视频分析只识别，不操作
        "templates": "templates",
        "plugins": "plugins",
        "window": None,
    }
    engine = Engine(cfg, root=ROOT, verbose=True).open()
    task_cls = TASKS.get("video_analyze")
    if task_cls is None:
        print("[错误] video_analyze 任务插件未加载")
        return 1

    task = task_cls(video=args.video, pipeline=args.pipeline, out=args.out,
                    min_gap_ms=args.min_gap_ms)
    try:
        timeline = task.run(engine)
    finally:
        engine.close()

    print("\n=== 分析完成 ===")
    print(f"  帧数: {timeline['frames']}  事件: {timeline['event_count']}  耗时: {timeline['elapsed_sec']}s")
    print(f"  时间线: {args.out}")
    for ev in timeline["events"][:15]:
        print(f"    [{ev['time_sec']:>7.2f}s] {ev['label']:<24} score={ev['score']:.3f} at {ev['center']}")
    if timeline["event_count"] > 15:
        print(f"    ... 共 {timeline['event_count']} 条（完整见 JSON）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
