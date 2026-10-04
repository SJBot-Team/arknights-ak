"""内核数据类型：帧、区域、匹配结果、动作、上下文。

设计原则（参考 MAA 与赛博塑料 prts+）：
- 坐标一律支持「绝对像素」与「相对归一化(0~1)」两种表达，跨分辨率可移植；
- 所有识别结果带 score 与 rect，便于流水线做阈值与位置决策；
- 内核不认识任何具体游戏，只认识这些抽象类型。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Rect:
    """矩形区域；绝对像素坐标（left, top, right, bottom），右下开区间。"""

    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top

    @property
    def center(self) -> tuple[int, int]:
        return (self.left + self.width // 2, self.top + self.height // 2)

    def as_tuple(self) -> tuple[int, int, int, int]:
        return (self.left, self.top, self.right, self.bottom)

    def offset(self, dx: int, dy: int) -> "Rect":
        return Rect(self.left + dx, self.top + dy, self.right + dx, self.bottom + dy)

    @staticmethod
    def from_rel(rel: tuple[float, float, float, float], base: "Rect", clamp: bool = True) -> "Rect":
        """相对(0~1) → 绝对；base 通常是窗口客户区或整屏。"""
        l = base.left + rel[0] * base.width
        t = base.top + rel[1] * base.height
        r = base.left + rel[2] * base.width
        b = base.top + rel[3] * base.height
        if clamp:
            l = max(base.left, min(l, base.right))
            t = max(base.top, min(t, base.bottom))
            r = max(base.left, min(r, base.right))
            b = max(base.top, min(b, base.bottom))
        return Rect(int(l), int(t), int(r), int(b))


@dataclass
class Frame:
    """一帧画面（BGR，numpy 数组）+ 元信息。"""

    image: Any                      # np.ndarray, HxWx3 BGR
    timestamp: float                # time.perf_counter()
    source: str = "screen"          # screen / window / video
    origin: tuple[int, int] = (0, 0)  # 图像左上角对应的屏幕坐标（窗口/区域裁剪时用）
    index: int = 0                  # 帧序号（视频源有用）

    @property
    def shape(self):
        return self.image.shape


@dataclass
class Match:
    """一次识别结果。"""

    label: str                      # 模板名/识别器给的标签
    rect: Rect                      # 命中区域（屏幕绝对坐标）
    score: float = 0.0
    recognizer: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def center(self) -> tuple[int, int]:
        return self.rect.center


@dataclass
class ActionSpec:
    """一个待执行动作（来自流水线 JSON）。"""

    kind: str                       # click / move / drag / key / text / scroll / sleep / custom:xxx
    params: dict = field(default_factory=dict)


@dataclass
class Context:
    """运行上下文：窗口信息、坐标系、统计、共享变量。"""

    window_title: str | None = None
    process_id: int | None = None
    client_rect: Rect | None = None  # 参考坐标系（窗口客户区），None 表示整屏
    screen_rect: Rect | None = None
    variables: dict = field(default_factory=dict)
    stats: dict = field(default_factory=dict)

    def base_rect(self) -> Rect:
        return self.client_rect or self.screen_rect or Rect(0, 0, 1920, 1080)
