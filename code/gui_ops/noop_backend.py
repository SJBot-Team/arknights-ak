# -*- coding: utf-8 -*-
"""noop_backend.py — 离线/干跑后端

两个用途：
1. `NoopBackend`：**真正的 dry-run**——只做前提检查与观察，不注入任何输入。
   agent 可以先用它把整份操作清单"空跑一遍"，验证清单本身、预期判据、
   状态文件格式是否自洽，再去接真后端。
2. `ScriptedBackend`：**离线回归**——按脚本吐预设结果，用来测试 AgentLoop 的
   重试/升级/改清单分支，不需要模拟器。`apps/selftest_loop.py` 用它。
"""
from __future__ import annotations

import os
import time

from contracts import Observation, OpStep, StepResult


class NoopBackend:
    name = "noop"

    def __init__(self, log=print, simulate_state: str = "unknown"):
        self.log = log
        self.simulate_state = simulate_state
        self.calls: list[str] = []

    def preflight(self) -> dict:
        return {"ok": True, "dry_run": True}

    def observe(self, shot_path: str | None = None) -> Observation:
        return Observation(ui_state=self.simulate_state,
                           extra={"dry_run": True, "note": "未接触游戏"})

    def step(self, op: OpStep) -> StepResult:
        self.calls.append(op.id)
        self.log(f"    [dry-run] 本应执行 {op.backend}:{op.payload.get('task', op.payload)}")
        # 干跑：只看"清单里写的预期"是否可判定，不去声称成功
        r = StepResult(step_id=op.id, backend=self.name, expect=op.expect)
        r.observed = {"dry_run": True, "task": op.payload.get("task"),
                      "ui_state": self.simulate_state}
        r.verdict = "ok"
        r.failure_class = "NONE"
        r.message = "dry-run：未执行，仅校验清单"
        return r.finish()

    def abort(self) -> None:
        pass


class ScriptedBackend:
    """按 `script[step_id]` 依次吐预设 StepResult。

    script 值形如:
      {"verdict":"ok"}                                  → 直接成功
      {"verdict":"error","failure_class":"TRANSIENT","message":"截图失败"}
      [ {...}, {...} ]                                  → 第 1、2 次调用分别返回
    """
    name = "scripted"

    def __init__(self, script: dict, log=print):
        self.script = script
        self.log = log
        self.n: dict[str, int] = {}
        self.calls: list[str] = []

    def preflight(self) -> dict:
        return {"ok": True}

    def observe(self, shot_path: str | None = None) -> Observation:
        return Observation(ui_state="battle", cost=10, extra={"scripted": True})

    def step(self, op: OpStep) -> StepResult:
        self.calls.append(op.id)
        k = self.n.get(op.id, 0)
        self.n[op.id] = k + 1
        v = self.script.get(op.id, {"verdict": "ok"})
        if isinstance(v, list):
            v = v[min(k, len(v) - 1)]
        r = StepResult(step_id=op.id, backend=self.name, expect=op.expect)
        r.verdict = v.get("verdict", "ok")
        r.failure_class = v.get("failure_class", "NONE" if r.verdict == "ok" else "SEMANTIC")
        r.message = v.get("message", "")
        r.observed = v.get("observed", {"task": op.payload.get("task")})
        r.diffs = v.get("diffs", [])
        time.sleep(float(v.get("delay", 0.0)))
        return r.finish()

    def abort(self) -> None:
        pass
