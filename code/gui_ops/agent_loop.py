# -*- coding: utf-8 -*-
"""agent_loop.py — ★ 核心：agent 驱动的操作闭环

## 闭环形状（用户指定）
    agent 列出操作清单 → MAA/prts+ 步进执行 → 执行结果与预期比对
      → 符合预期 ⇒ 执行下一步
      → 不符合预期 ⇒ agent 介入修改操作清单
      → 任务完成或终止

## 谁调谁
    AgentLoop 是**唯一的执行器**；它持有 Plan（操作清单）与各 Backend。
    它自己就能处理：预期比对、自动重试、状态落盘。
    它**只有**在 `should_escalate()` 为真时才停下来找 agent（人/LLM），
    并把 `Escalation`（含 StepResult + 最近状态 + 可选项）交出去。

## 状态文件（两条，都是 append-only，可断点续跑）
    <run_dir>/state.jsonl   每步一行 JSON（StepResult.to_dict）
    <run_dir>/plan.json     当前生效的操作清单（agent 每次修订都会覆盖并 +rev）
    <run_dir>/shots/*.png   每步前后的截图证据

## 失败分类 → 处置（唯一分叉点，见 contracts.FAILURE_ACTIONS）
    TRANSIENT → 自动重试（最多 op.retry 次）
    SEMANTIC / ENV / FATAL / DATA → escalate（交 agent 改清单）
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field

from contracts import (FAILURE_ACTIONS, OpStep, Plan, StepResult, should_auto_retry,
                       should_escalate, should_stop)


@dataclass
class Escalation:
    """交给 agent 的"我卡住了"包。agent 只需读这个就能决定怎么改清单。"""
    step: OpStep
    result: StepResult
    reason: str
    options: list[dict] = field(default_factory=list)
    run_dir: str = ""
    plan_rev: int = 1

    def to_dict(self) -> dict:
        return {"reason": self.reason, "step": self.step.__dict__,
                "result": self.result.to_dict(), "options": self.options,
                "run_dir": self.run_dir, "plan_rev": self.plan_rev}

    def text(self) -> str:
        r = self.result
        lines = [
            f"[需要 agent 决策] 步骤 {self.step.id}（{self.step.backend}/{self.step.phase}）",
            f"  分类: {r.failure_class} — {FAILURE_ACTIONS.get(r.failure_class, {}).get('desc','')}",
            f"  判定: {r.verdict}   原因: {r.message}",
        ]
        if r.diffs:
            lines.append("  预期差异: " + "；".join(r.diffs))
        if r.observed:
            lines.append("  实读: " + json.dumps(r.observed, ensure_ascii=False)[:400])
        if r.evidence:
            lines.append("  证据: " + json.dumps(r.evidence, ensure_ascii=False))
        lines.append(f"  当前清单: {self.run_dir}\\plan.json  (rev {self.plan_rev})")
        if self.options:
            lines.append("  可选处置: " + " | ".join(o.get("label", "") for o in self.options))
        return "\n".join(lines)


class AgentLoop:
    def __init__(self, plan: Plan, backends: dict, run_dir: str, log=print):
        self.plan = plan
        self.backends = backends                     # {"maa": MaaBackend, "prts": PrtsBackend}
        self.run_dir = run_dir
        self.log = log
        self.records: list[StepResult] = []
        # ★ 已"被解决"的失败下标：重试成功、或已被 agent 改清单取代的旧尝试。
        #   它们仍留在 state.jsonl 里（审计），但不计入最终 ok=False。
        self._resolved: set[int] = set()
        os.makedirs(os.path.join(run_dir, "shots"), exist_ok=True)

    def _resolve_prior(self, step_id: str) -> None:
        for i, r in enumerate(self.records):
            if r.step_id == step_id and not r.ok:
                self._resolved.add(i)

    # ------------------------------------------------------------ 落盘
    def _append_state(self, rec: StepResult, attempt: int, note: str = "") -> None:
        d = rec.to_dict()
        d["attempt"] = attempt
        d["plan_rev"] = self.plan.rev
        d["note"] = note
        with open(os.path.join(self.run_dir, "state.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")

    def save_plan(self) -> str:
        p = os.path.join(self.run_dir, "plan.json")
        self.plan.save(p)
        return p

    # ------------------------------------------------------------ 单步
    def _one_attempt(self, op: OpStep, attempt: int) -> StepResult:
        be = self.backends.get(op.backend)
        if be is None:
            r = StepResult(step_id=op.id, backend=op.backend, verdict="error",
                           failure_class="ENV", message=f"未注册后端 {op.backend}")
            return r.finish()
        shot = os.path.join(self.run_dir, "shots", f"{op.id}_a{attempt}_before.png")
        try:
            ob = be.observe(shot) if hasattr(be, "observe") else None
        except Exception:                                        # noqa: BLE001
            ob = None
        self.log(f"  → {op.id} [{op.backend}/{op.phase}] {op.desc or op.payload.get('task','')}")
        t0 = time.time()
        try:
            r = be.step(op)
        except Exception as e:                                   # noqa: BLE001
            r = StepResult(step_id=op.id, backend=op.backend, verdict="error",
                           failure_class="FATAL", message=f"{type(e).__name__}: {e}")
            r.finish()
        r.started_at = t0
        if ob is not None:
            r.evidence.setdefault("before", ob.to_dict())
        self.log(f"     verdict={r.verdict} class={r.failure_class} "
                 f"{r.duration_s}s  {r.message[:120]}")
        return r

    # ------------------------------------------------------------ 主循环
    def run(self, on_escalate=None, max_steps: int = 200) -> dict:
        """跑完清单。`on_escalate(esc) -> dict|None`：
        返回 {"action": "retry"|"skip"|"abort"|"plan", "plan": {...}} 来处置；
        返回 None 或 "abort" 则结束。**这就是 agent 的注入点。**
        """
        self.save_plan()
        i, n = 0, 0
        while i < len(self.plan.steps) and n < max_steps:
            n += 1
            op = self.plan.steps[i]
            attempt = 0
            while True:
                r = self._one_attempt(op, attempt)
                self.records.append(r)
                self._append_state(r, attempt)
                if r.ok:
                    self._resolve_prior(op.id)      # 之前的失败尝试已被解决
                    break
                if should_auto_retry(r, attempt, op):
                    attempt += 1
                    self.log(f"     ↻ {r.failure_class} 可重试（{attempt}/{op.retry}）")
                    self._append_state(r, attempt, note="auto-retry")
                    time.sleep(min(2.0 * attempt, 6.0))
                    continue
                if op.optional:
                    self.log(f"     ⊘ 可选步骤失败，跳过：{op.id}")
                    r.verdict = "skipped"
                    break
                esc = Escalation(step=op, result=r, run_dir=self.run_dir,
                                 plan_rev=self.plan.rev,
                                 reason=r.message or r.verdict,
                                 options=self._options(r, op))
                self.log(esc.text())
                dec = on_escalate(esc) if on_escalate else None
                act = (dec or {}).get("action", "abort")
                if act == "retry":
                    attempt += 1
                    continue
                if act == "skip":
                    break
                if act == "plan" and dec.get("plan"):
                    # agent 修订了清单 ⇒ 此前所有失败尝试都被"取代"，不计入失败
                    self._resolved |= set(range(len(self.records)))
                    self.plan = Plan.from_dict(dec["plan"])
                    self.plan.rev += 1
                    self.save_plan()
                    self.log(f"     ✎ agent 修订清单 → rev {self.plan.rev}，"
                             f"{len(self.plan.steps)} 步")
                    i = -1                       # 从新清单头部重来
                    break
                # abort
                return self._report(i, aborted_by=esc)
            if should_stop(self.records[-1]):
                return self._report(i, aborted_by=None)
            i += 1
        return self._report(i)

    @staticmethod
    def _options(r: StepResult, op: OpStep) -> list[dict]:
        fc = r.failure_class
        o = []
        if FAILURE_ACTIONS.get(fc, {}).get("retry"):
            o.append({"action": "retry", "label": "重试本步"})
        o.append({"action": "skip", "label": "跳过本步"})
        o.append({"action": "plan", "label": "改操作清单（agent 出修订版）"})
        o.append({"action": "abort", "label": "终止"})
        return o

    def _report(self, at: int, aborted_by: Escalation | None = None) -> dict:
        ok = sum(1 for r in self.records if r.ok)
        bad = [r for i, r in enumerate(self.records)
               if not r.ok and i not in self._resolved]
        return {"ok": aborted_by is None and not bad,
                "steps_done": at, "steps_total": len(self.plan.steps),
                "attempts": len(self.records), "ok_count": ok,
                "resolved_failures": len(self._resolved),
                "failed": [{"step": r.step_id, "class": r.failure_class,
                            "verdict": r.verdict, "message": r.message[:200]}
                           for r in bad],
                "aborted_at": None if not aborted_by else aborted_by.step.id,
                "plan_rev": self.plan.rev, "run_dir": self.run_dir}

    def close(self) -> None:
        for b in self.backends.values():
            try:
                b.abort()
            except Exception:                                    # noqa: BLE001
                pass
