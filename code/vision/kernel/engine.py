"""内核引擎：把采集 / 识别 / 动作 / 流水线拼起来，跑 60FPS 主循环。

内核不包含任何游戏逻辑——所有具体能力都来自 plugins/。换需求时替换插件即可。
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable

from . import registry
from . import window as window_mod
from .capture import BaseCapture, pick_capture
from .input import perform as perform_action
from .pipeline import Pipeline, Runner, StepResult
from .types import ActionSpec, Context, Frame, Match, Rect
from .vision import TemplateLibrary

DEFAULT_CONFIG = {
    "target_fps": 60,
    "capture": ["bettercam", "dxcam", "mss"],
    "input": ["directinput", "sendinput"],
    "window": None,          # {"title": "明日方舟", "process": null, "auto_focus": false}
    "region": None,          # [left, top, right, bottom] 绝对像素；缺省=窗口客户区或整屏
    "templates": "templates",
    "plugins": "plugins",
    "capture_kwargs": {},         # 传给采集后端的构造参数（如 video 的 path/skip）
    "capture_region_rel": None,   # 相对窗口的裁剪 [l,t,r,b]（0~1），只抓需要的区域以省算力
}


class Engine:
    def __init__(self, config: dict | None = None, root: str | Path | None = None, verbose: bool = True):
        self.root = Path(root or Path(__file__).resolve().parent.parent)
        self.cfg = {**DEFAULT_CONFIG, **(config or {})}
        self.verbose = verbose
        self.ctx = Context(variables={}, stats={})
        self.capture: BaseCapture | None = None
        self.input: Any = None
        self.templates = TemplateLibrary(self.root / self.cfg["templates"])
        self.loaded_plugins: list[str] = []
        self.action_count = 0

    # ---------------- 生命周期 ----------------
    def open(self) -> "Engine":
        plugins_dir = self.root / self.cfg["plugins"]
        # 让 plugins/ 下的模块可按顶层包名导入（capture.* / recognize.* / action.* / task.*）
        import sys
        if str(plugins_dir) not in sys.path:
            sys.path.insert(0, str(plugins_dir))
        self.loaded_plugins = registry.load_plugins(plugins_dir, verbose=self.verbose)
        if self.verbose:
            print(f"[engine] 插件已加载: {json.dumps(registry.describe(), ensure_ascii=False)}")
            print(f"[engine] 模板库: {len(self.templates.names())} 个")

        # 窗口
        win_cfg = self.cfg.get("window")
        hwnd = None
        if win_cfg:
            win = window_mod.find_window(win_cfg.get("title", ""), win_cfg.get("process"))
            if win is None:
                raise RuntimeError(f"未找到窗口: {win_cfg}")
            hwnd = win["hwnd"]
            self.ctx.window_title = win["title"]
            self.ctx.process_id = win["pid"]
            self.ctx.client_rect = window_mod.client_rect(hwnd)
            if win_cfg.get("auto_focus"):
                window_mod.activate(hwnd)
            if self.verbose:
                print(f"[engine] 窗口: {win['title']} pid={win['pid']} 客户区={self.ctx.client_rect.as_tuple()}")

        # 采集区域
        region = None
        if self.cfg.get("capture_region_rel") and self.ctx.client_rect:
            rel = self.cfg["capture_region_rel"]
            region = Rect.from_rel(tuple(rel), self.ctx.client_rect)  # type: ignore[arg-type]
        elif self.cfg.get("region"):
            r = self.cfg["region"]
            region = Rect(int(r[0]), int(r[1]), int(r[2]), int(r[3]))
        elif self.ctx.client_rect:
            region = self.ctx.client_rect

        self.capture = pick_capture(self.cfg["capture"], region=region,
                                    **self.cfg.get("capture_kwargs", {}))
        self.ctx.screen_rect = Rect(0, 0, *self._screen_size())
        if self.verbose:
            print(f"[engine] 采集后端: {self.capture.name} 标称上限 {self.capture.fps_cap} FPS 区域={None if region is None else region.as_tuple()}")

        # 输入
        for name in self.cfg["input"]:
            cls = registry.ACTIONS.get(f"input:{name}")
            if cls:
                try:
                    self.input = cls()
                    if self.verbose:
                        print(f"[engine] 输入后端: {name}")
                    break
                except Exception as exc:
                    if self.verbose:
                        print(f"[engine] 输入后端 {name} 不可用: {exc!r}")
        if self.input is None:
            if self.verbose:
                print("[engine] 警告: 无可用输入后端（只识别不操作）")
        return self

    def _screen_size(self) -> tuple[int, int]:
        try:
            import ctypes
            user32 = ctypes.windll.user32
            return (user32.GetSystemMetrics(0), user32.GetSystemMetrics(1))
        except Exception:
            return (1920, 1080)

    def close(self) -> None:
        if self.capture:
            try:
                self.capture.close()
            except Exception:
                pass

    # ---------------- 基本能力 ----------------
    def grab(self, region: Rect | None = None) -> Frame:
        assert self.capture is not None, "engine 未 open()"
        frame = self.capture.grab(region)
        # 采集区域可能被裁剪：把 origin 记为绝对坐标，供匹配结果换算
        return frame

    def _resolve_roi(self, roi: Rect | None) -> Rect | None:
        """把请求的 ROI 与采集区域求交，避免越界。"""
        if roi is None:
            return None
        return roi

    def recognize(self, spec: dict, frame: Frame, ctx: Context, roi: Rect | None = None,
                  label: str = "") -> Match | None:
        """按 spec["type"] 派发到识别器插件；返回最佳匹配或 None。"""
        if not spec:
            return None
        kind = spec.get("type", "template")
        cls = registry.RECOGNIZERS.get(kind)
        if cls is None:
            raise KeyError(f"未注册的识别器类型: {kind}（可用: {sorted(registry.RECOGNIZERS)}）")
        recognizer = cls()

        img = frame.image
        origin = frame.origin
        if roi is not None:
            # 裁剪到帧内
            fl, ft = frame.origin
            fh, fw = img.shape[:2]
            l = max(roi.left, fl)
            t = max(roi.top, ft)
            r = min(roi.right, fl + fw)
            b = min(roi.bottom, ft + fh)
            if r <= l or b <= t:
                return None
            img = img[t - ft:b - ft, l - fl:r - fl]
            origin = (l, t)

        t0 = time.perf_counter()
        matches = recognizer.run(img, spec, ctx, origin, label=label, engine=self)  # type: ignore[attr-defined]
        cost_ms = (time.perf_counter() - t0) * 1000
        ctx.stats.setdefault("recognize_ms", {})
        key = f"{kind}:{spec.get('name', spec.get('template', ''))}"
        st = ctx.stats["recognize_ms"].setdefault(key, {"n": 0, "total": 0.0, "max": 0.0})
        st["n"] += 1
        st["total"] += cost_ms
        st["max"] = max(st["max"], cost_ms)
        if not matches:
            return None
        best = max(matches, key=lambda m: m.score)
        best.recognizer = kind
        return best

    def do(self, spec: ActionSpec, ctx: Context) -> None:
        if self.input is None:
            return
        perform_action(spec, ctx, self.input)
        self.action_count += 1

    # ---------------- 便捷 API ----------------
    def find(self, template: str, threshold: float = 0.85, region: Rect | None = None,
             scales: list[float] | None = None) -> Match | None:
        frame = self.grab(region)
        spec = {"type": "template", "name": template, "threshold": threshold, "scales": scales}
        return self.recognize(spec, frame, self.ctx, region, label=template)

    def click(self, template: str, threshold: float = 0.85, offset: tuple[int, int] = (0, 0)):
        m = self.find(template, threshold)
        if not m:
            return False
        self.do(ActionSpec("click", {"x": m.center[0] + offset[0], "y": m.center[1] + offset[1]}), self.ctx)
        return True

    # ---------------- 主循环 ----------------
    def run(self, pipeline: Pipeline | str | Path | None = None, seconds: float | None = None,
            max_steps: int | None = None, on_step: Callable[[Frame, StepResult | None], None] | None = None,
            stop_when_finished: bool = True) -> dict:
        """跑主循环；pipeline 为 None 时只采集+计时（用于基准测试）。"""
        assert self.capture is not None
        runner = None
        if pipeline is not None:
            pipe = pipeline if isinstance(pipeline, Pipeline) else Pipeline.load(pipeline)
            runner = Runner(pipe)

        target_fps = float(self.cfg.get("target_fps", 60))
        period = 1.0 / target_fps if target_fps > 0 else 0.0
        t_start = time.perf_counter()
        frames = 0
        loop_fps_ts = t_start
        loop_fps_n = 0
        measured = []
        grab_total = 0.0
        step_total = 0.0
        last_result: StepResult | None = None

        while True:
            t_loop = time.perf_counter()
            if seconds is not None and (t_loop - t_start) >= seconds:
                break
            t_g = time.perf_counter()
            frame = self.grab()
            grab_total += time.perf_counter() - t_g
            frames += 1
            loop_fps_n += 1

            if runner is not None and not runner.finished:
                t_s = time.perf_counter()
                last_result = runner.step(self, self.ctx, frame)
                step_total += time.perf_counter() - t_s
                if on_step:
                    on_step(frame, last_result)
                if stop_when_finished and runner.finished:
                    break
                if max_steps is not None and len(runner.history) >= max_steps:
                    break
            elif on_step:
                on_step(frame, None)

            # 统计
            now = time.perf_counter()
            if now - loop_fps_ts >= 1.0:
                measured.append(loop_fps_n / (now - loop_fps_ts))
                loop_fps_ts, loop_fps_n = now, 0

            # 节拍
            if period:
                dt = time.perf_counter() - t_loop
                if dt < period:
                    time.sleep(max(0.0, period - dt - 0.001))
                    while time.perf_counter() - t_loop < period:
                        pass

        total = time.perf_counter() - t_start
        stats = {
            "frames": frames,
            "seconds": round(total, 3),
            "loop_fps": round(frames / total, 2) if total else 0.0,
            "grab_ms_avg": round(grab_total / frames * 1000, 3) if frames else 0.0,
            "step_ms_avg": round(step_total / frames * 1000, 3) if frames else 0.0,
            "per_second_fps": [round(x, 1) for x in measured],
            "actions": self.action_count,
            "recognizers": {k: {"n": v["n"], "avg_ms": round(v["total"] / max(1, v["n"]), 3), "max_ms": round(v["max"], 3)}
                            for k, v in self.ctx.stats.get("recognize_ms", {}).items()},
        }
        if runner is not None:
            stats["pipeline"] = runner.summary()
            stats["last_result"] = None if last_result is None else {
                "node": last_result.node_id, "matched": last_result.matched,
                "next": last_result.next_node, "timed_out": last_result.timed_out,
            }
        self.ctx.stats.update(stats)
        return stats
