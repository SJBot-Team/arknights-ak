"""采集抽象：所有截屏后端实现同一接口，内核按名称选取。

接口契约（插件作者只需实现这两个方法）：
    open() -> None
    grab(region: Rect | None) -> Frame
    close() -> None
    @property fps_cap -> float   # 该后端标称上限，供调度参考
"""
from __future__ import annotations

import time
from typing import Protocol

from .types import Frame, Rect


class CaptureBackend(Protocol):
    name: str
    fps_cap: float

    def open(self) -> None: ...
    def grab(self, region: Rect | None = None) -> Frame: ...
    def close(self) -> None: ...


class BaseCapture:
    """提供默认实现，具体后端覆盖 grab()。"""

    name = "base"
    fps_cap = 60.0
    source_kind = "screen"

    def __init__(self, region: Rect | None = None):
        self.region = region
        self._t0 = time.perf_counter()
        self._n = 0

    def open(self) -> None:  # pragma: no cover - 由子类实现
        raise NotImplementedError

    def grab(self, region: Rect | None = None) -> Frame:  # pragma: no cover
        raise NotImplementedError

    def close(self) -> None:  # pragma: no cover
        pass

    def _frame(self, image, region: Rect | None) -> Frame:
        self._n += 1
        r = region or self.region
        origin = (r.left, r.top) if r else (0, 0)
        return Frame(image=image, timestamp=time.perf_counter(),
                     source=self.source_kind, origin=origin, index=self._n)

    def measured_fps(self) -> float:
        dt = time.perf_counter() - self._t0
        return self._n / dt if dt > 0 else 0.0


def region_to_xywh(region: Rect | None) -> tuple[int, int, int, int] | None:
    if region is None:
        return None
    return (region.left, region.top, region.width, region.height)


def pick_capture(preferred: list[str], **kwargs) -> BaseCapture:
    """按偏好顺序选择可用后端（前一个失败自动降级）。"""
    from .registry import CAPTURES

    errors = []
    for name in preferred:
        cls = CAPTURES.get(name)
        if cls is None:
            errors.append(f"{name}: 未注册")
            continue
        try:
            inst = cls(**kwargs)
            inst.open()
            return inst
        except Exception as exc:
            errors.append(f"{name}: {exc!r}")
    raise RuntimeError("没有可用的采集后端：" + "; ".join(errors))
