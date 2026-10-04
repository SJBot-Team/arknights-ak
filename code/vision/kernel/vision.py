"""视觉识别：模板库（热加载）+ 模板匹配（OpenCV，多尺度 + 掩码 + NMS）。

模板库设计（"增减识别功能"的最轻方式）：
- templates/ 下放 PNG/JPG，文件名即模板名（可带子目录，如 main/start.png → "main/start"）；
- 运行中自动检测目录变化并重载 → 加一个识别目标 = 丢一张图 + 在流水线里引用它。
"""
from __future__ import annotations

import time
from pathlib import Path

import cv2
import numpy as np

from .types import Match, Rect

METHODS = {
    "ccoeff": cv2.TM_CCOEFF_NORMED,
    "ccorr": cv2.TM_CCORR_NORMED,
    "sqdiff": cv2.TM_SQDIFF_NORMED,
}
IMG_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}


class TemplateLibrary:
    def __init__(self, root: str | Path, auto_reload: bool = True):
        self.root = Path(root)
        self.auto_reload = auto_reload
        self._cache: dict[str, np.ndarray] = {}
        self._stamp: float = 0.0
        if self.auto_reload:
            self.reload()

    # ---------- 目录扫描 ----------
    def _scan(self) -> dict[str, Path]:
        found: dict[str, Path] = {}
        if not self.root.exists():
            return found
        for p in self.root.rglob("*"):
            if p.is_file() and p.suffix.lower() in IMG_EXT:
                rel = p.relative_to(self.root).with_suffix("")
                found[rel.as_posix()] = p
        return found

    def _dir_stamp(self) -> float:
        latest = 0.0
        for p in self._scan().values():
            latest = max(latest, p.stat().st_mtime)
        return latest

    def reload(self, force: bool = False) -> int:
        stamp = self._dir_stamp()
        if not force and stamp <= self._stamp and self._cache:
            return len(self._cache)
        files = self._scan()
        cache: dict[str, np.ndarray] = {}
        for name, path in files.items():
            img = cv2.imread(str(path), cv2.IMREAD_COLOR)
            if img is not None:
                cache[name] = img
        self._cache = cache
        self._stamp = stamp
        return len(cache)

    # ---------- 访问 ----------
    def names(self) -> list[str]:
        if self.auto_reload:
            self.reload()
        return sorted(self._cache)

    def get(self, name: str) -> np.ndarray:
        """按名取模板；名字可省略扩展名，可带子目录。"""
        if self.auto_reload:
            self.reload()
        key = name.replace("\\", "/").rsplit(".", 1)[0] if "." in Path(name).name else name.replace("\\", "/")
        if key in self._cache:
            return self._cache[key]
        raise KeyError(f"模板未找到: {name}（可用: {', '.join(self.names()[:10])} ...）")


def _nms_from_map(score_map: np.ndarray, tpl: np.ndarray, threshold: float,
                  origin: tuple[int, int], max_results: int, label: str,
                  inv: float = 1.0) -> list[Match]:
    """从已经算好的分数图生成 Match（供 OpenCL 路径复用）。"""
    ys, xs = np.where(score_map >= threshold)
    h, w = tpl.shape[:2]
    boxes: list[tuple[Rect, float]] = []
    for y, x in zip(ys.tolist(), xs.tolist()):
        l = int(round(x * inv)) + origin[0]
        t = int(round(y * inv)) + origin[1]
        r = int(round((x + w) * inv)) + origin[0]
        b = int(round((y + h) * inv)) + origin[1]
        boxes.append((Rect(l, t, r, b), float(score_map[y, x])))
    return [Match(label=label, rect=r, score=s, recognizer="template")
            for r, s in _nms(boxes, max_results=max_results)]


def _nms(boxes: list[tuple[Rect, float]], iou_thr: float = 0.3, max_results: int = 1):
    boxes = sorted(boxes, key=lambda b: -b[1])
    keep: list[tuple[Rect, float]] = []
    for rect, score in boxes:
        ok = True
        for kr, _ in keep:
            # 交集
            il, it = max(rect.left, kr.left), max(rect.top, kr.top)
            ir, ib = min(rect.right, kr.right), min(rect.bottom, kr.bottom)
            iw, ih = max(0, ir - il), max(0, ib - it)
            inter = iw * ih
            union = rect.width * rect.height + kr.width * kr.height - inter
            if union > 0 and inter / union > iou_thr:
                ok = False
                break
        if ok:
            keep.append((rect, score))
        if len(keep) >= max_results:
            break
    return keep


def find_template(image: np.ndarray, template: np.ndarray, threshold: float = 0.85,
                  method: str = "ccoeff", mask: np.ndarray | None = None,
                  max_results: int = 1, scales: list[float] | None = None,
                  origin: tuple[int, int] = (0, 0), label: str = "",
                  downscale: float = 1.0) -> list[Match]:
    """在 image 中查找 template；返回按分数降序的 Match 列表（坐标为屏幕绝对坐标）。

    性能提示（实测）：
    - 全帧 1080p 匹配 ≈ 124 ms；ROI 140x140 ≈ 0.9 ms；降采样 0.25x ≈ 8 ms。
    - 想跑 60 FPS：优先用流水线节点的 roi 限定小区域（MAA 亦如此），
      大区域再叠加 downscale（识别坐标会自动换算回原分辨率）。
    """
    if image is None or template is None:
        return []
    if template.shape[0] > image.shape[0] or template.shape[1] > image.shape[1]:
        return []

    if downscale and downscale != 1.0:
        image = cv2.resize(image, None, fx=downscale, fy=downscale, interpolation=cv2.INTER_AREA)
        template = cv2.resize(template, None, fx=downscale, fy=downscale, interpolation=cv2.INTER_AREA)
        if mask is not None:
            mask = cv2.resize(mask, (template.shape[1], template.shape[0]), interpolation=cv2.INTER_NEAREST)
        if template.shape[0] < 4 or template.shape[1] < 4:
            return []

    inv = 1.0 / downscale if downscale else 1.0
    m = METHODS.get(method, cv2.TM_CCOEFF_NORMED)
    best: list[tuple[Rect, float]] = []

    for scale in (scales or [1.0]):
        tpl = template
        if scale != 1.0:
            tpl = cv2.resize(template, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
            if tpl.shape[0] < 4 or tpl.shape[1] < 4:
                continue
        if tpl.shape[0] > image.shape[0] or tpl.shape[1] > image.shape[1]:
            continue
        res = cv2.matchTemplate(image, tpl, m, mask=mask)
        if m == cv2.TM_SQDIFF_NORMED:
            score_map = 1.0 - res
        else:
            score_map = res
        ys, xs = np.where(score_map >= threshold)
        h, w = tpl.shape[:2]
        for y, x in zip(ys.tolist(), xs.tolist()):
            l = int(round(x * inv)) + origin[0]
            t = int(round(y * inv)) + origin[1]
            r = int(round((x + w) * inv)) + origin[0]
            b = int(round((y + h) * inv)) + origin[1]
            best.append((Rect(l, t, r, b), float(score_map[y, x])))

    out = []
    for rect, score in _nms(best, max_results=max_results):
        out.append(Match(label=label, rect=rect, score=score, recognizer="template"))
    return out
