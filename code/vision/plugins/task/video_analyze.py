"""任务插件：视频分析（场景②）——把攻略视频当帧源，用同一套模板/流水线识别操作步骤。"""
from __future__ import annotations

import json
import time
from pathlib import Path

from kernel.pipeline import Pipeline, Runner
from kernel.registry import task
from kernel.types import Context


@task("video_analyze")
class VideoAnalyzeTask:
    """在视频上跑流水线识别，输出「帧号 → 时间 → 命中标签/位置」的事件时间线。

    参数（dict）：
        video        视频路径
        pipeline     流水线 JSON 路径（节点 interval_ms 会被忽略，逐帧全跑）
        out          时间线输出 JSON 路径
        min_gap_ms   同一标签的最小记录间隔（去抖），默认 500
        report_every 每多少帧打印一次进度，默认 300
    """

    def __init__(self, video: str, pipeline: str | Path, out: str | Path,
                 min_gap_ms: int = 500, report_every: int = 300, detect_only: bool = True):
        self.video = video
        self.pipeline_path = str(pipeline)
        self.out = str(out)
        self.min_gap_ms = min_gap_ms
        self.report_every = report_every
        self.detect_only = detect_only   # 视频分析只识别、不执行动作（安全）

    def run(self, engine) -> dict:
        pipe = Pipeline.load(self.pipeline_path)
        runner = Runner(pipe)
        events: list[dict] = []
        last_seen: dict[str, float] = {}
        frames = 0
        t0 = time.perf_counter()

        # 视频模式：关闭动作执行（安全），改为记录
        original_do = engine.do
        recorded: list[dict] = []

        def record_only(spec, ctx: Context):
            recorded.append({"kind": spec.kind, "params": spec.params})

        engine.do = record_only  # type: ignore[assignment]
        try:
            while not getattr(engine.capture, "eof", False):
                frame = engine.grab()
                frames += 1
                before = len(recorded)
                res = runner.step(engine, engine.ctx, frame)
                if res.matched and res.match is not None:
                    now_ms = time.perf_counter() * 1000
                    if now_ms - last_seen.get(res.match.label, 0) >= self.min_gap_ms:
                        last_seen[res.match.label] = now_ms
                        pos_sec = frames / max(1.0, getattr(engine.capture, "native_fps", 30.0))
                        events.append({
                            "frame": frames,
                            "time_sec": round(pos_sec, 3),
                            "label": res.match.label,
                            "score": round(res.match.score, 4),
                            "center": list(res.match.center),
                            "actions": recorded[before:],
                        })
                if self.report_every and frames % self.report_every == 0:
                    print(f"  ... {frames} 帧, {len(events)} 事件, {frames / (time.perf_counter() - t0):.1f} 帧/秒")
        finally:
            engine.do = original_do  # type: ignore[assignment]

        timeline = {
            "video": self.video,
            "pipeline": pipe.name,
            "frames": frames,
            "events": events,
            "elapsed_sec": round(time.perf_counter() - t0, 2),
            "event_count": len(events),
        }
        Path(self.out).parent.mkdir(parents=True, exist_ok=True)
        Path(self.out).write_text(json.dumps(timeline, ensure_ascii=False, indent=2), encoding="utf-8")
        return timeline
