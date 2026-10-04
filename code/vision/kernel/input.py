"""输入抽象：鼠标/键盘动作，后端可替换（SendInput / DirectInput / ADB / 硬件 HID）。

统一入口：InputBackend.perform(ActionSpec)，动作类型由动作插件实现；
坐标支持绝对像素与相对归一化（相对 ctx.base_rect()，即窗口客户区）。
"""
from __future__ import annotations

import time
from typing import Protocol

from .types import ActionSpec, Context, Rect


class InputBackend(Protocol):
    name: str

    def click(self, x: int, y: int, button: str = "left", clicks: int = 1) -> None: ...
    def move(self, x: int, y: int, duration: float = 0.0) -> None: ...
    def drag(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.2) -> None: ...
    def scroll(self, dy: int) -> None: ...
    def key(self, key: str, presses: int = 1, down: bool = False) -> None: ...
    def text(self, s: str) -> None: ...


class BaseInput:
    name = "base"

    def click(self, x, y, button="left", clicks=1):  # pragma: no cover
        raise NotImplementedError

    def move(self, x, y, duration=0.0):  # pragma: no cover
        raise NotImplementedError

    def drag(self, x1, y1, x2, y2, duration=0.2):  # pragma: no cover
        raise NotImplementedError

    def scroll(self, dy):  # pragma: no cover
        raise NotImplementedError

    def key(self, key, presses=1, down=False):  # pragma: no cover
        raise NotImplementedError

    def text(self, s):  # pragma: no cover
        raise NotImplementedError


def resolve_point(params: dict, ctx: Context) -> tuple[int, int]:
    """支持三种写法：
    - {"x": 100, "y": 200}                      绝对像素
    - {"rel_x": 0.5, "rel_y": 0.5}              相对参考矩形（赛博塑料 prts+ 风格）
    - {"target": "match_label"}                 使用流水线中最近一次识别的命中中心
    """
    if "x" in params and "y" in params:
        return int(params["x"]), int(params["y"])
    if "rel_x" in params and "rel_y" in params:
        base = ctx.base_rect()
        return (int(base.left + params["rel_x"] * base.width),
                int(base.top + params["rel_y"] * base.height))
    if "target" in params:
        m = ctx.variables.get(f"match:{params['target']}")
        if m is not None:
            return m.center
        raise KeyError(f"未找到识别目标 {params['target']}（请先在该流水线节点识别）")
    raise ValueError(f"无法解析坐标参数: {params}")


def perform(spec: ActionSpec, ctx: Context, backend: InputBackend) -> None:
    """动作派发（内核侧统一处理，插件只需提供原语）。"""
    k, p = spec.kind, spec.params
    if k == "click":
        x, y = resolve_point(p, ctx)
        backend.click(x, y, p.get("button", "left"), int(p.get("clicks", 1)))
    elif k == "move":
        x, y = resolve_point(p, ctx)
        backend.move(x, y, float(p.get("duration", 0.0)))
    elif k == "drag":
        x1, y1 = resolve_point(p, ctx)
        x2 = int(p["x2"]) if "x2" in p else int(p["to_x"])
        y2 = int(p["y2"]) if "y2" in p else int(p["to_y"])
        backend.drag(x1, y1, x2, y2, float(p.get("duration", 0.2)))
    elif k == "scroll":
        backend.scroll(int(p.get("dy", -1)))
    elif k == "key":
        backend.key(p["key"], int(p.get("presses", 1)), bool(p.get("down", False)))
    elif k == "text":
        backend.text(p["value"])
    elif k == "sleep":
        time.sleep(float(p.get("seconds", 0.1)))
    else:
        raise ValueError(f"未知动作类型: {k}")
