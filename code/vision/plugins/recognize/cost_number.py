"""费用数字识别器（cost_number）—— 从画面读右下角费用数字

实机用途：在没有外部费用尺时，用「费用数字 + 脚本自己的消耗记账」构造绝对帧时钟
（见 `plugins/clock/cost_ruler.py::CostNumberClock`）。

spec 参数：
  roi        费用数字区域（相对 0~1 或绝对像素四元组；本机 MuMu 1920×1080 实测 (1795,730,1915,805)）
  templates  数字模板 JSON（`video_cost_timeline.py bootstrap` 产出的 0~9 模板；跨分辨率可复用）
  grow       字形高度过滤比例（默认 0.5）
  debug      为真时在 extra 里返回字形数

返回 Match(label="cost_number", extra={cost, digits, glyphs, confidence, roi})
"""
from __future__ import annotations

import os
import sys

from kernel.registry import recognizer
from kernel.types import Match, Rect

_APP_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                        '..', '..', 'apps'))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)


def _resolve_roi(spec: dict, image, origin):
    roi = spec.get('roi')
    if not roi:
        return None
    if len(roi) == 4 and all(isinstance(v, (int, float)) and v > 1.5 for v in roi):
        x0, y0, x1, y1 = [int(v) for v in roi]
    else:
        h, w = image.shape[:2]
        x0, y0, x1, y1 = int(roi[0] * w), int(roi[1] * h), int(roi[2] * w), int(roi[3] * h)
    h, w = image.shape[:2]
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(w, x1), min(h, y1)
    if x1 <= x0 or y1 <= y0:
        return None
    return x0, y0, x1, y1


@recognizer("cost_number")
class CostNumberRecognizer:
    def run(self, image, spec: dict, ctx, origin, label: str = "", engine=None) -> list[Match]:
        if image is None or getattr(image, 'size', 0) == 0:
            return []
        r = _resolve_roi(spec, image, origin)
        if r is None:
            return []
        x0, y0, x1, y1 = r
        crop = image[y0:y1, x0:x1]
        try:
            from video_cost_timeline import glyphs_in_roi, classify, load_templates
        except Exception:
            return []
        tpl_path = spec.get('templates')
        tpl = spec.get('_tpl_cache')
        if tpl is None:
            tpl = load_templates(tpl_path) if tpl_path else {}
            spec['_tpl_cache'] = tpl
        if not tpl:
            return []
        gl = glyphs_in_roi(crop, int(spec.get('x_min', 0)))
        val, conf = classify(gl, tpl) if gl else (None, 0.0)
        if val is None or not val.isdigit():
            return []
        rect = Rect(origin[0] + x0, origin[1] + y0, origin[0] + x1, origin[1] + y1)
        return [Match(label=label or 'cost_number', rect=rect, score=conf,
                      recognizer='cost_number',
                      extra={'cost': int(val), 'digits': val, 'glyphs': len(gl),
                             'confidence': round(conf, 4), 'roi': [x0, y0, x1, y1]})]
