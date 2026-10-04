"""技能栏识别器（skill_ready）—— 技能按钮就绪 / SP 充能

为什么需要它（knowledge/04/41 §7.15）：技能"激活之后"的状态无法仅靠表值推算——
是否仍在激活、弹药余量、按钮是否就绪，都只有画面知道。因此打图端要真正与模拟器同构，
必须能读技能栏。

三种模式（spec.mode）：
  ready    技能按钮 ROI → 就绪 / 未就绪 / 激活中（默认）
           原理：就绪=高亮**金色**按钮；充能中=暗灰低饱和；激活中=**另一种色相**（蓝/青）。
           判据：①"彩色亮像素"占比 color_ratio（gray ≥ bright_min 且 sat ≥ ready_sat）
                 ②这些像素的主导色相 hue 是否落在 ready_hue ± ready_hue_tol 内。
  sp_bar   条状 SP 条 ROI → 填充比例（从左往右亮像素占比），返回 sp_ratio。
  sp_arc   环形 SP 表 ROI → 填充比例（按角度采样，正上方起顺时针；按径向带取最大亮度）。

spec 参数：
  mode           'ready' | 'sp_bar' | 'sp_arc'
  bright_thr     亮像素阈值（0~255，默认 170）——sp_bar/sp_arc 用它判定"整条是否全暗"
  bright_min     ready 模式下的亮度下限（默认 100）
  ready_ratio    color_ratio 阈值（默认 0.20）
  ready_sat      饱和度下限（默认 0.35）
  ready_hue      就绪态主导色相（度，默认 45=金色）；None/负数表示不判色相
  ready_hue_tol  色相容差（度，默认 45）
  invert         反向
  samples        环形采样点数（默认 180）
  band           环形径向采样带宽（像素，默认 3）

返回 Match(label="skill_ready", extra={ready, state, sp_ratio, color_ratio, saturation, hue, mode})
"""
from __future__ import annotations

import colorsys

from kernel.registry import recognizer
from kernel.types import Match, Rect


def _gray_sat_hue(image):
    """返回 (gray, sat, hue_deg)；gray 0~255，sat 0~1，hue 0~360。"""
    import numpy as np
    bgr = image[..., :3] if image.ndim == 3 else image[..., None].repeat(3, 2)
    f = bgr.astype('float32') / 255.0
    b, g, r = f[..., 0], f[..., 1], f[..., 2]
    mx = f.max(axis=2)
    mn = f.min(axis=2)
    diff = mx - mn
    sat = diff / (mx + 1e-6)
    gray = bgr.astype('float32').mean(axis=2)
    hue = np.zeros_like(mx)
    nz = diff > 1e-6
    # 标准 RGB 色相公式（输入已拆成 r/g/b）
    r_is_max = nz & (mx == r)
    g_is_max = nz & (mx == g) & ~r_is_max
    b_is_max = nz & (mx == b) & ~r_is_max & ~g_is_max
    hue[r_is_max] = (60 * ((g - b) / (diff + 1e-6)) % 360)[r_is_max]
    hue[g_is_max] = (60 * ((b - r) / (diff + 1e-6)) + 120)[g_is_max]
    hue[b_is_max] = (60 * ((r - g) / (diff + 1e-6)) + 240)[b_is_max]
    return gray, sat, hue


@recognizer("skill_ready")
class SkillReadyRecognizer:
    def run(self, image, spec: dict, ctx, origin, label: str = "", engine=None) -> list[Match]:
        if image is None or getattr(image, 'size', 0) == 0:
            return []
        import numpy as np
        h, w = image.shape[:2]
        mode = str(spec.get('mode', 'ready'))
        bright_thr = float(spec.get('bright_thr', 170.0))
        gray, sat, hue = _gray_sat_hue(image)

        sp_ratio = None
        if mode == 'sp_bar':
            col = gray.max(axis=0)
            peak = float(col.max()) if col.size else 0.0
            if peak < bright_thr:                     # 整条全暗 → 空
                sp_ratio = 0.0
            else:
                lit = np.where(col >= peak * float(spec.get('min_ratio', 0.55)))[0]
                sp_ratio = float((lit.max() + 1) / max(1, w)) if lit.size else 0.0
        elif mode == 'sp_arc':
            n = int(spec.get('samples', 180))
            band = int(spec.get('band', 3))
            cy, cx = (h - 1) / 2.0, (w - 1) / 2.0
            r_out = min(h, w) / 2.0 - 1.0
            vals = []
            for k in range(n):
                ang = -np.pi / 2 + 2 * np.pi * k / n          # 正上方起顺时针
                best = 0.0
                for rr in range(max(1, int(r_out) - band), int(r_out) + 1):
                    y = int(round(cy + rr * np.sin(ang)))
                    x = int(round(cx + rr * np.cos(ang)))
                    if 0 <= y < h and 0 <= x < w:
                        best = max(best, float(gray[y, x]))
                vals.append(best)
            vals = np.asarray(vals)
            peak = float(vals.max()) if vals.size else 0.0
            if peak < bright_thr:
                sp_ratio = 0.0
            else:
                lit = vals >= peak * float(spec.get('min_ratio', 0.6))
                # 取最长连续亮段（跨首尾）占整圈比例
                idx = np.where(lit)[0]
                if idx.size == 0:
                    sp_ratio = 0.0
                else:
                    best_len, cur_len = 1, 1
                    for a, b in zip(idx, idx[1:]):
                        cur_len = cur_len + 1 if b == a + 1 else 1
                        best_len = max(best_len, cur_len)
                    if lit[0] and lit[-1] and idx.size < len(lit):
                        head = 0
                        while head < len(lit) and lit[head]:
                            head += 1
                        tail = 0
                        while tail < len(lit) and lit[len(lit) - 1 - tail]:
                            tail += 1
                        best_len = max(best_len, head + tail)
                    sp_ratio = float(best_len / len(lit))

        bright_min = float(spec.get('bright_min', 100.0))
        sat_thr = float(spec.get('ready_sat', 0.35))
        colored = (gray >= bright_min) & (sat >= sat_thr)
        color_ratio = float(colored.mean())
        mean_sat = float(sat.mean())
        main_hue = float(hue[colored].mean()) if colored.any() else -1.0

        ready_hue = spec.get('ready_hue', 45.0)
        hue_tol = float(spec.get('ready_hue_tol', 45.0))
        hue_ok = True
        if mode == 'ready' and ready_hue is not None and float(ready_hue) >= 0 and main_hue >= 0:
            d = abs(main_hue - float(ready_hue))
            d = min(d, 360 - d)
            hue_ok = d <= hue_tol

        if sp_ratio is not None:
            ready = bool(sp_ratio >= float(spec.get('sp_ready_ratio', 0.995)))
            state = 'ready' if ready else 'charging'
        else:
            ready = bool(color_ratio >= float(spec.get('ready_ratio', 0.20)) and hue_ok)
            if color_ratio < float(spec.get('ready_ratio', 0.20)):
                state = 'charging'
            elif not hue_ok:
                state = 'active'
            else:
                state = 'ready'
        if spec.get('invert'):
            ready = not ready
            state = 'ready' if ready else 'charging'

        rect = Rect(origin[0], origin[1], origin[0] + w, origin[1] + h)
        return [Match(label=label or 'skill_ready', rect=rect,
                      score=1.0 if ready else 0.0, recognizer='skill_ready',
                      extra={'ready': ready, 'state': state, 'sp_ratio': sp_ratio,
                             'color_ratio': round(color_ratio, 4),
                             'saturation': round(mean_sat, 4), 'hue': round(main_hue, 1),
                             'mode': mode})]
