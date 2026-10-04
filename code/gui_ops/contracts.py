# -*- coding: utf-8 -*-
"""contracts.py — agent 驱动操作流程的**接口约定**（唯一真源）

本模块只放数据结构，不含任何 IO。MAA 后端、prts+ 后端、agent 循环都只依赖这里，
因此三者可以独立替换。

## 名词
- **Plan 操作清单**：agent 产出的"要做哪些步"的有序列表。
- **OpStep 一步**：一条可执行的操作（交给某个 backend）。
- **Observation 观察**：执行前后从游戏读回的状态（截图路径 + 界面语义 + 关键数值）。
- **StepResult 一步结果**：执行 + 观察 + 判定（verdict / failure_class）。
- **Verdict 判定**：ok / mismatch / error / timeout —— 决定"下一步"还是"叫 agent"。

## 闭环
    agent --(Plan)--> AgentLoop --(OpStep)--> Backend
                           ^                     |
                           |                     v
                     (Plan 修订) <-- AgentLoop <-- StepResult(含 Observation)
       verdict==ok            ⇒ 自动走下一步
       failure_class 可重试   ⇒ 自动重试
       否则                   ⇒ escalate：把 StepResult + 状态文件交给 agent 修 Plan
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

# ---------------------------------------------------------------- 失败分类
# ★ 这是"哪些能自动重试、哪些必须 agent 决策"的唯一判据表。
FAILURE_ACTIONS: dict[str, dict[str, Any]] = {
    # 可自动重试：环境抖动，重试大概率就好
    "TRANSIENT": {"retry": True, "escalate": False,
                  "desc": "超时 / 截图失败 / 加载慢 / 动画未结束"},
    # 不可重试、必须换做法：识别成功但语义不是预期（点错、界面不对）
    "SEMANTIC": {"retry": False, "escalate": True,
                 "desc": "识别到了但目标不对：界面语义不符、点了没生效、状态量不匹配"},
    # 环境前提缺失：重试无意义，需要上游先修环境
    "ENV": {"retry": False, "escalate": True,
            "desc": "模拟器未启动/未连接/窗口找不到/ADB 掉线"},
    # 任务链自身报错：停下来，交 agent 判断是否可绕过
    "FATAL": {"retry": False, "escalate": True, "stop": True,
              "desc": "TaskChainError / 进程崩溃 / 任务链内部错误"},
    # 需要人工或 agent 补数据（例如轴表缺列）
    "DATA": {"retry": False, "escalate": True, "stop": True,
             "desc": "输入数据不合法或缺失（轴表列缺失、坐标无法映射）"},
}

Verdict = Literal["ok", "mismatch", "error", "timeout", "skipped"]


# ---------------------------------------------------------------- Plan
@dataclass
class OpStep:
    """一步操作。backend 字段决定谁执行；payload 由 backend 自行解释。"""
    id: str
    backend: str                       # "maa" | "prts" | "vision" | "noop"
    phase: str = "outgame"             # "outgame"（局外，MAA） | "ingame"（局内，prts+）
    desc: str = ""
    payload: dict = field(default_factory=dict)
    # expect 是**可判定的预期**；AgentLoop 用 sub-verifier 逐个比对 observed
    expect: dict = field(default_factory=dict)
    retry: int = 0                     # 自动重试次数（上限）
    timeout: float = 60.0
    optional: bool = False             # 失败不阻塞（如"顺手领个奖励"）

    @staticmethod
    def from_dict(d: dict) -> "OpStep":
        d = dict(d)
        return OpStep(
            id=str(d.pop("id")),
            backend=str(d.pop("backend", "noop")),
            phase=str(d.pop("phase", "outgame")),
            desc=str(d.pop("desc", "")),
            payload=dict(d.pop("payload", {}) or {}),
            expect=dict(d.pop("expect", {}) or {}),
            retry=int(d.pop("retry", 0)),
            timeout=float(d.pop("timeout", 60.0)),
            optional=bool(d.pop("optional", False)),
        )


@dataclass
class Plan:
    plan_id: str
    stage: str = ""
    steps: list[OpStep] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    rev: int = 1                       # agent 每改一次 +1

    @staticmethod
    def from_dict(d: dict) -> "Plan":
        return Plan(
            plan_id=str(d.get("plan_id", "plan")),
            stage=str(d.get("stage", "")),
            steps=[OpStep.from_dict(s) for s in d.get("steps", [])],
            notes=list(d.get("notes", [])),
            rev=int(d.get("rev", 1)),
        )

    @staticmethod
    def load(path: str) -> "Plan":
        with open(path, encoding="utf-8") as f:
            return Plan.from_dict(json.load(f))

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    def by_id(self, sid: str) -> OpStep | None:
        for s in self.steps:
            if s.id == sid:
                return s
        return None


# ---------------------------------------------------------------- Observation
@dataclass
class Observation:
    """从游戏读回的状态。**语义优先**：截图只是证据，判据是 ui_state / 数值。"""
    ui_state: str = "unknown"          # battle / squad / viewport / terminal / home / unknown
    cost: int | None = None            # 费用数字
    cost_phase: float | None = None    # 费用条秒内相位 0~1
    frame_now: int | None = None       # 由费用推算的帧号（1 秒 = 30 帧）
    extra: dict = field(default_factory=dict)   # 各 backend 私有字段
    shot: str | None = None            # 截图落盘路径（证据）

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------- StepResult
@dataclass
class StepResult:
    step_id: str
    backend: str = ""
    verdict: Verdict = "error"
    failure_class: str = "FATAL"
    started_at: float = field(default_factory=time.time)
    ended_at: float = 0.0
    expect: dict = field(default_factory=dict)
    observed: dict = field(default_factory=dict)
    events: list[dict] = field(default_factory=list)   # backend 原始事件（MAA 回调 / prts+ 日志行）
    diffs: list[str] = field(default_factory=list)     # 逐项比对差异
    message: str = ""
    evidence: dict = field(default_factory=dict)       # {"shot": path, "log": path, ...}

    @property
    def duration_s(self) -> float:
        return round(max(0.0, self.ended_at - self.started_at), 3)

    @property
    def ok(self) -> bool:
        return self.verdict == "ok"

    def finish(self) -> "StepResult":
        self.ended_at = time.time()
        return self

    def to_dict(self) -> dict:
        d = asdict(self)
        d["duration_s"] = self.duration_s
        d["ok"] = self.ok
        return d


# ---------------------------------------------------------------- 判定策略
def classify_failure(verdict: Verdict, why: str = "") -> str:
    """把"为什么失败"映射到失败分类。这是自动重试 / 交 agent 的**唯一分叉点**。"""
    w = (why or "").lower()
    if verdict == "ok":
        return "NONE"
    if verdict == "timeout":
        return "TRANSIENT"
    # 环境类关键词（MAA ConnectionInfo / prts+ 窗口找不到）
    for k in ("screencapfailed", "connect", "not connected", "window", "adb",
              "handle", "no device", "未找到窗口", "未连接", "模拟器"):
        if k in w:
            return "ENV"
    # 任务链内部错误
    for k in ("taskchainerror", "subtaskerror", "internalerror", "initfailed",
              "crash", "exception"):
        if k in w:
            return "FATAL"
    # 语义不符
    for k in ("expect", "mismatch", "not ", "did not", "未", "不符", "没生效",
              "state", "ui_state"):
        if k in w:
            return "SEMANTIC"
    return "SEMANTIC"


def should_auto_retry(fr: StepResult, attempt: int, op: OpStep) -> bool:
    a = FAILURE_ACTIONS.get(fr.failure_class, {})
    return bool(a.get("retry")) and attempt < op.retry


def should_escalate(fr: StepResult) -> bool:
    return bool(FAILURE_ACTIONS.get(fr.failure_class, {}).get("escalate", True))


def should_stop(fr: StepResult) -> bool:
    return bool(FAILURE_ACTIONS.get(fr.failure_class, {}).get("stop", False))
