"""模板匹配识别器（主力）：从模板库取图，在 ROI 内匹配。

spec 参数：
    name/template  模板名（templates/ 下的相对路径，省略扩展名）
    threshold      阈值，默认 0.85
    method         ccoeff(默认) / ccorr / sqdiff
    scales         多尺度列表，如 [0.9, 1.0, 1.1]（应对分辨率差异，代价 ×N）
    max_results    返回上限，默认 1
    mask           掩码模板名（可选）
    downscale      降采样系数（如 0.5 → 快 4 倍，坐标自动换算回原分辨率）
    ocl            true 时走 OpenCL（实测全帧 123ms→48ms，ROI 10ms→5ms）

性能实测（1080p，64x64 模板）：
    全帧 124ms | 降采样0.5x 34ms | 降采样0.25x 8ms | ROI 140x140 0.87ms | ROI+OpenCL 5ms(400x300)
→ 想稳定 60 FPS：优先给节点加 roi（小区域），必要时再叠加 downscale。
"""
from __future__ import annotations

import cv2

from kernel.registry import recognizer
from kernel.types import Match
from kernel.vision import find_template


@recognizer("template")
class TemplateRecognizer:
    def run(self, image, spec: dict, ctx, origin, label: str = "", engine=None) -> list[Match]:
        name = spec.get("name") or spec.get("template")
        if not name or engine is None:
            return []
        try:
            tpl = engine.templates.get(name)
        except KeyError:
            return []

        mask = None
        if spec.get("mask"):
            try:
                mask = cv2.cvtColor(engine.templates.get(spec["mask"]), cv2.COLOR_BGR2GRAY)
            except KeyError:
                mask = None

        kwargs = dict(
            threshold=float(spec.get("threshold", 0.85)),
            method=spec.get("method", "ccoeff"),
            mask=mask,
            max_results=int(spec.get("max_results", 1)),
            scales=spec.get("scales"),
            origin=origin,
            label=label or name,
            downscale=float(spec.get("downscale", 1.0) or 1.0),
        )

        if spec.get("ocl"):
            cv2.ocl.setUseOpenCL(True)
            try:
                u_img, u_tpl = cv2.UMat(image), cv2.UMat(tpl)
                res = cv2.matchTemplate(u_img, u_tpl, cv2.TM_CCOEFF_NORMED)
                import numpy as np
                score_map = res.get()
                import kernel.vision as kv
                return kv._nms_from_map(score_map, tpl, kwargs["threshold"], origin, kwargs["max_results"], kwargs["label"])
            except Exception:
                pass  # 回退 CPU 路径

        return find_template(image, tpl, **kwargs)

