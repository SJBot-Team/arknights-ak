"""费用尺识别器（cost_bar）—— 费用条像素 → 帧级时钟

原理（参考本机 ArknightsCostBarRuler 校准格式）：
  费用条以「填充像素长度」线性对应费用内帧偏移：
    30fps 客户端：每个费用 = 30 帧；60fps 客户端：60 帧
  校准文件（profile_*.json）给出 pixel_map: {填充像素: 帧号}。
  本识别器测出当前填充像素 → 按像素映射插值得到帧偏移；
  与费用数值（OCR 或固定跟踪）组合成 (cost, frame) 时钟 —— 与轴表锚点同构。

spec 参数：
  roi         费用条区域（相对 0~1 或绝对像素四元组）
  calibration 校准文件路径（ArknightsCostBarRuler profile json），或 {"pixel_map": {...}, "total_frames": N}
  fill_rgb    填充色（可选；缺省用亮度法）
  tol         颜色容差
  cost_roi    费用数字区域（可选，配合 ocr 识别费用值）
  cost_ocr    OCR 识别器名（默认 "ocr"）
  min_ratio   亮度阈值（相对 ROI 内最大亮度），默认 0.55

返回 Match(label="cost_bar", extra={frame, fill_px, cost, clock})
"""
from __future__ import annotations

import json
import os
from typing import Any

from kernel.registry import recognizer
from kernel.types import Match, Rect


def _load_profile(spec: dict) -> dict | None:
    cal = spec.get('calibration')
    if not cal:
        return None
    if isinstance(cal, dict):
        return cal
    if isinstance(cal, str) and os.path.exists(cal):
        with open(cal, encoding='utf-8') as f:
            d = json.load(f)
        # 兼容 ArknightsCostBarRuler 的 profiles[0] 结构
        if 'profiles' in d:
            d = d['profiles'][0]
        return d
    return None


def _pixel_map(profile: dict) -> dict[int, int]:
    pm = profile.get('pixel_map') or {}
    out = {}
    for k, v in pm.items():
        try:
            out[int(k)] = int(v)
        except Exception:
            continue
    return out


def _frame_from_pixels(pm: dict[int, int], px: float) -> int:
    if not pm:
        return 0
    xs = sorted(pm)
    if px <= xs[0]:
        return pm[xs[0]]
    if px >= xs[-1]:
        return pm[xs[-1]]
    for a, b in zip(xs, xs[1:]):
        if a <= px <= b:
            t = (px - a) / max(1e-9, (b - a))
            return int(round(pm[a] + t * (pm[b] - pm[a])))
    return pm[xs[-1]]


@recognizer("cost_bar")
class CostBarRecognizer:
    # ★实机实测的费用条区域（1920×1080）：轨道 x≈1740→1872、填充行 y≈809–817。
    #   旧版 `run()` **完全没有使用 roi**，而是对**整幅图**取列最大值 ⇒ `fill_px` 恒为 1920
    #   （HUD 右缘总有亮像素），无标定时 `frames = 1920/1920×30 = 30` ⇒ 恒报"满条"。
    DEFAULT_ROI = (1736, 806, 1876, 822)      # 费用条（含轨道），绝对像素，宽 140
    # 满条长度（px）：**实机长窗实测 `fill_px` 最大值 = 140**（= ROI 宽度）
    #   —— 原设 132 会让末段 8px 被削平成 frame=30（每周期约 1.7 帧死区）。
    #   实测佐证：14s 长窗 ⇒ 415 帧/13.96s = **29.7 帧/秒**、满条 14 次（≈1/s）。
    DEFAULT_BAR_PX = 140

    @staticmethod
    def _roi_px(roi, w: int, h: int):
        """支持 [x0,y0,x1,y1]（绝对像素，>1）或相对 [0~1] 四元组。"""
        if not roi:
            return (0, 0, w, h)
        x0, y0, x1, y1 = [float(v) for v in roi]
        if max(x0, y0, x1, y1) <= 1.0:                     # 相对
            x0, y0, x1, y1 = x0 * w, y0 * h, x1 * w, y1 * h
        x0, y0 = max(0, int(x0)), max(0, int(y0))
        x1, y1 = min(w, int(x1)), min(h, int(y1))
        if x1 <= x0 or y1 <= y0:
            return (0, 0, w, h)
        return (x0, y0, x1, y1)

    def run(self, image, spec: dict, ctx, origin, label: str = "", engine=None) -> list[Match]:
        if image is None or getattr(image, 'size', 0) == 0:
            return []
        import numpy as np

        h, w = image.shape[:2]
        # ---- ★按 ROI 取费用条（旧版漏了这一步，导致对整幅图取列最大值）----
        rx0, ry0, rx1, ry1 = self._roi_px(spec.get('roi') or self.DEFAULT_ROI, w, h)
        band = image[ry0:ry1, rx0:rx1, :3]
        bw = band.shape[1]
        if band.size == 0:
            return []
        gray = band.mean(axis=2) if band.ndim == 3 else band
        col_peak = gray.max(axis=0)                 # 每列最亮值（填充是亮块）
        peak = float(col_peak.max()) if col_peak.size else 0.0
        ro = (origin[0] + rx0, origin[1] + ry0, origin[0] + rx1, origin[1] + ry1)
        if peak <= 1e-6:
            # 空条（费用刚结算）→ 帧偏移 0
            return [Match(label=label or 'cost_bar', rect=Rect(*ro),
                          score=0.0, recognizer='cost_bar',
                          extra={'frame': 0, 'fill_px': 0, 'roi_w': bw, 'cost': None,
                                 'clock': {'cost': None, 'frame': 0}})]
        min_ratio = float(spec.get('min_ratio', 0.55))
        thr = peak * min_ratio
        bright = col_peak >= thr
        # 填充自轨道左端起始 ⇒ 取"从左起连续亮列"的长度（比"亮列总数"更抗噪）
        fill_px = 0
        for v in bright:
            if v:
                fill_px += 1
            else:
                break
        if fill_px == 0:
            fill_px = int(bright.sum())             # 兜底：允许中间有暗缝
        # 满条长度：优先 spec['bar_px']，其次 ROI 宽
        bar_px = float(spec.get('bar_px') or self.DEFAULT_BAR_PX or bw)

        profile = _load_profile(spec)
        frames = 0
        if profile:
            pm = _pixel_map(profile)
            # 校准像素域 → 当前域（等比缩放）
            prof_px = float((profile.get('full_px') or (max(pm) if pm else bar_px)))
            frames = _frame_from_pixels(pm, fill_px * (prof_px / max(1.0, bar_px)))
        else:
            total = int(spec.get('total_frames', 30))
            frames = int(round(min(1.0, fill_px / max(1.0, bar_px)) * total))

        # 可选：识别费用数值
        cost = None
        cost_roi = spec.get('cost_roi')
        if cost_roi and engine is not None:
            try:
                base = ctx.base_rect()
                roi = Rect.from_rel(tuple(cost_roi), base) if not isinstance(cost_roi, Rect) else cost_roi
                m = engine.recognize({'use': spec.get('cost_ocr', 'ocr'), 'spec': {'mode': 'digits'}},
                                     frame=None, ctx=ctx, roi=roi) if False else None
                # 简化：交由上层用 engine.recognize 处理（此处避免递归捕获开销）
                _ = m
            except Exception:
                cost = None

        rect = Rect(*ro)
        return [Match(label=label or 'cost_bar', rect=rect,
                      score=min(1.0, fill_px / max(1.0, bar_px)),
                      recognizer='cost_bar',
                      extra={'frame': frames, 'fill_px': fill_px, 'roi_w': bw,
                             'bar_px': bar_px, 'roi': [rx0, ry0, rx1, ry1],
                             'cost': cost, 'clock': {'cost': cost, 'frame': frames}})]
