"""颜色识别器：判断某点/某区域的像素颜色是否落入目标范围。

spec 参数：
    rgb       目标颜色 [r, g, b]
    tol       容差（每通道），默认 12
    point     绝对 [x, y] 或 {"rel_x":0.5,"rel_y":0.5}；缺省用 ROI 中心
    mode      any(默认) / all —— 对 region_grid 采样点生效
    grid      在 ROI 内按 n×n 采样，默认 1
"""
from __future__ import annotations

from kernel.registry import recognizer
from kernel.types import Match, Rect


@recognizer("color")
class ColorRecognizer:
    def run(self, image, spec: dict, ctx, origin, label: str = "", engine=None) -> list[Match]:
        if image is None or image.size == 0:
            return []
        target = spec.get("rgb") or spec.get("color")
        if target is None:
            return []
        tol = int(spec.get("tol", 12))
        h, w = image.shape[:2]

        # 采样点集合
        grid = int(spec.get("grid", 1) or 1)
        pts: list[tuple[int, int]] = []
        if "point" in spec:
            p = spec["point"]
            if isinstance(p, dict):
                base = ctx.base_rect()
                px = int(base.left + p.get("rel_x", 0.5) * base.width) - origin[0]
                py = int(base.top + p.get("rel_y", 0.5) * base.height) - origin[1]
            else:
                px, py = int(p[0]) - origin[0], int(p[1]) - origin[1]
            pts.append((px, py))
        else:
            for iy in range(grid):
                for ix in range(grid):
                    pts.append((int((ix + 0.5) * w / grid), int((iy + 0.5) * h / grid)))

        hits = 0
        for (px, py) in pts:
            if not (0 <= px < w and 0 <= py < h):
                continue
            b, g, r = (int(v) for v in image[py, px][:3])
            if abs(r - target[0]) <= tol and abs(g - target[1]) <= tol and abs(b - target[2]) <= tol:
                hits += 1
        need = len(pts) if spec.get("mode", "any") == "all" else 1
        if hits >= need and pts:
            px, py = pts[0]
            rect = Rect(origin[0] + max(0, px - 1), origin[1] + max(0, py - 1),
                        origin[0] + px + 2, origin[1] + py + 2)
            return [Match(label=label or "color", rect=rect, score=1.0, recognizer="color",
                          extra={"hits": hits, "sampled": len(pts)})]
        return []
