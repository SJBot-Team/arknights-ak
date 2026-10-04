"""高速截屏后端（bettercam / dxcam）：DXGI 桌面复制，60~240 FPS。"""
from __future__ import annotations

import numpy as np

from kernel.capture import BaseCapture, region_to_xywh
from kernel.registry import capture
from kernel.types import Frame, Rect


class _DxgiCapture(BaseCapture):
    module_name = "bettercam"

    def open(self) -> None:
        mod = __import__(self.module_name)
        self._camera = mod.create(output_idx=0, output_color="BGR")
        self.fps_cap = 240.0
        # 预热一帧，避免首帧耗时计入
        try:
            self._camera.grab()
        except Exception:
            pass

    def grab(self, region: Rect | None = None) -> Frame:
        r = region or self.region
        xywh = region_to_xywh(r)
        img = None
        for _ in range(2):  # DXGI 偶尔返回 None（画面未更新），重试一次
            img = self._camera.grab(region=xywh) if xywh else self._camera.grab()
            if img is not None:
                break
        if img is None:
            img = np.zeros((r.height if r else 1080, r.width if r else 1920, 3), dtype=np.uint8)
        return self._frame(img, r)

    def close(self) -> None:
        try:
            self._camera.release()
        except Exception:
            pass


@capture("bettercam")
class BetterCamCapture(_DxgiCapture):
    name = "bettercam"
    module_name = "bettercam"


@capture("dxcam")
class DxcamCapture(_DxgiCapture):
    name = "dxcam"
    module_name = "dxcam"
