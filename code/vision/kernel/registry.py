"""插件注册表：内核只依赖这里的抽象，具体实现放在 plugins/ 下。

扩展方式（这是"换需求只换插件"的关键）：
    from kernel.registry import capture, recognizer, action, task

    @capture("bettercam")
    class BetterCamCapture(CaptureBackend): ...

新增一个后端/识别器/动作，只需在 plugins/ 下新建模块并注册同名；内核与流水线不动。
plugins/ 目录会在 engine 启动时被自动导入（见 load_plugins）。
"""
from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path
from typing import Any, Callable, Type

CAPTURES: dict[str, type] = {}
RECOGNIZERS: dict[str, type] = {}
ACTIONS: dict[str, type] = {}
TASKS: dict[str, Any] = {}


def _register(bucket: dict, name: str) -> Callable[[Type], Type]:
    def deco(cls: Type) -> Type:
        bucket[name] = cls
        cls.plugin_name = name  # type: ignore[attr-defined]
        return cls
    return deco


def capture(name: str):
    return _register(CAPTURES, name)


def recognizer(name: str):
    return _register(RECOGNIZERS, name)


def action(name: str):
    return _register(ACTIONS, name)


def task(name: str):
    return _register(TASKS, name)


def load_plugins(plugins_root: str | Path, verbose: bool = False) -> list[str]:
    """递归导入 plugins/ 下的所有模块，触发注册装饰器。返回已加载模块名。"""
    import sys

    root = Path(plugins_root)
    loaded: list[str] = []
    if not root.exists():
        return loaded
    # 让插件模块可按顶层包名导入（capture.* / recognize.* / action.* / task.*）
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    for mod in pkgutil.walk_packages([str(root)], prefix=""):
        name = mod.name
        if name.startswith("_"):
            continue
        try:
            importlib.import_module(name)
            loaded.append(name)
            if verbose:
                print(f"  [plugin] {name}")
        except Exception as exc:  # 单个插件失败不影响内核
            print(f"  [plugin] {name} 加载失败: {exc!r}")
    return loaded


def describe() -> dict[str, list[str]]:
    return {
        "capture": sorted(CAPTURES),
        "recognize": sorted(RECOGNIZERS),
        "action": sorted(ACTIONS),
        "task": sorted(TASKS),
    }
