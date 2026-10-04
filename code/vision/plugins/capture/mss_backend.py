"""mss 采集后端（兼容性兜底）+ 视频文件帧源（场景②）。"""
from __future__ import annotations

import numpy as np

from kernel.capture import BaseCapture, region_to_xywh
from kernel.registry import capture
from kernel.types import Frame, Rect


@capture("mss")
class MssCapture(BaseCapture):
    name = "mss"
    fps_cap = 60.0

    def open(self) -> None:
        import mss
        self._sct = mss.mss()

    def grab(self, region: Rect | None = None) -> Frame:
        r = region or self.region
        if r is None:
            mon = self._sct.monitors[1]
            shot = self._sct.grab(mon)
            img = np.asarray(shot)[:, :, :3]
            return self._frame(np.ascontiguousarray(img), None)
        shot = self._sct.grab({"left": r.left, "top": r.top, "width": r.width, "height": r.height})
        img = np.asarray(shot)[:, :, :3]
        return self._frame(np.ascontiguousarray(img), r)

    def close(self) -> None:
        try:
            self._sct.close()
        except Exception:
            pass


@capture("video")
class VideoCapture(BaseCapture):
    """把视频文件当作"屏幕"：场景② 用同一内核识别攻略视频。

    支持参数（构造时传入）：
        path        视频路径
        skip        每 N 帧取 1 帧（默认 1=每帧）
        start_sec   起始时间
        end_sec     结束时间
        loop        是否循环
    """
    name = "video"
    fps_cap = 1000.0
    source_kind = "video"

    def __init__(self, path: str, skip: int = 1, start_sec: float = 0.0,
                 end_sec: float | None = None, loop: bool = False, region: Rect | None = None, **_):
        super().__init__(region=region)
        self.path = path
        self.skip = max(1, int(skip))
        self.start_sec = start_sec
        self.end_sec = end_sec
        self.loop = loop
        self._eof = False

    def open(self) -> None:
        import cv2
        self._cap = cv2.VideoCapture(self.path)
        if not self._cap.isOpened():
            raise RuntimeError(f"无法打开视频: {self.path}")
        self.native_fps = self._cap.get(cv2.CAP_PROP_FPS) or 30.0
        if self.start_sec:
            self._cap.set(cv2.CAP_PROP_POS_MSEC, self.start_sec * 1000)

    def grab(self, region: Rect | None = None) -> Frame:
        import cv2
        img = None
        for _ in range(self.skip):
            ok, frame = self._cap.read()
            if not ok:
                self._eof = True
                if self.loop:
                    self._cap.set(cv2.CAP_PROP_POS_MSEC, self.start_sec * 1000)
                    ok, frame = self._cap.read()
                    if not ok:
                        break
                else:
                    break
            img = frame
            pos_sec = self._cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
            if self.end_sec and pos_sec >= self.end_sec:
                self._eof = True
                break
        if img is None:
            img = np.zeros((1080, 1920, 3), dtype=np.uint8)
        return self._frame(img, region)

    @property
    def eof(self) -> bool:
        return self._eof

    def close(self) -> None:
        try:
            self._cap.release()
        except Exception:
            pass
