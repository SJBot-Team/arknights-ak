"""vision 内核（可插拔视觉控制引擎）。

导出常用符号，便于插件与 app 直接 `from kernel import Engine, Rect, Match`。
注意：注册装饰器以 `*_plugin` 别名导出，避免遮蔽同名子模块
（`kernel.capture` / `kernel.recognize` 等），插件请从 `kernel.registry` 导入装饰器。
"""
from .engine import Engine
from .pipeline import Pipeline, Runner, StepResult
from .registry import action as action_plugin
from .registry import capture as capture_plugin
from .registry import describe, load_plugins
from .registry import recognizer as recognizer_plugin
from .registry import task as task_plugin
from .types import ActionSpec, Context, Frame, Match, Rect
from .vision import TemplateLibrary, find_template

__all__ = [
    "Engine", "Pipeline", "Runner", "StepResult",
    "capture_plugin", "recognizer_plugin", "action_plugin", "task_plugin",
    "describe", "load_plugins",
    "ActionSpec", "Context", "Frame", "Match", "Rect",
    "TemplateLibrary", "find_template",
]
