# -*- coding: utf-8 -*-
"""selftest_loop.py — **离线回归**：用 ScriptedBackend 验证 AgentLoop 的四条分支

不需要模拟器、不需要游戏。验证：
  A 全绿：逐步 ok
  B 自动重试：TRANSIENT 失败 → 重试后成功（不需要 agent）
  C 升级改清单：SEMANTIC 失败 → 调 on_escalate → 返回修订 plan → 从新清单重跑
  D 终止：FATAL 失败 → 停止并出报告
  E 干跑：NoopBackend 跑整份 plan 不报错
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8")

from agent_loop import AgentLoop                    # noqa: E402
from contracts import Plan                          # noqa: E402
from noop_backend import NoopBackend, ScriptedBackend  # noqa: E402

PASS = FAIL = 0


def check(name: str, cond: bool, extra: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✅ {name} {extra}")
    else:
        FAIL += 1
        print(f"  ❌ {name} {extra}")


def mkphase(tag: str, steps: list[dict]) -> tuple[Plan, str, dict]:
    d = tempfile.mkdtemp(prefix=f"guiops_{tag}_")
    plan = Plan.from_dict({"plan_id": tag, "rev": 1, "steps": steps})
    return plan, d, {}


def step(sid: str, **kw) -> dict:
    d = {"id": sid, "backend": "scripted", "phase": "outgame",
         "payload": {"task": sid}}
    d.update(kw)
    return d


def case_A() -> None:
    print("\n[A] 全绿：逐步 ok")
    plan, rd, _ = mkphase("A", [step("a1"), step("a2"), step("a3")])
    be = ScriptedBackend({})
    rep = AgentLoop(plan, {"scripted": be}, rd, log=lambda *_: None).run()
    check("全部执行", be.calls == ["a1", "a2", "a3"], str(be.calls))
    check("报告 ok", rep["ok"], json.dumps(rep, ensure_ascii=False)[:120])


def case_B() -> None:
    print("\n[B] 自动重试：TRANSIENT 失败 → 重试后成功（不叫 agent）")
    plan, rd, _ = mkphase("B", [step("b1", retry=2), step("b2")])
    be = ScriptedBackend({
        "b1": [{"verdict": "timeout", "failure_class": "TRANSIENT", "message": "截图超时"},
               {"verdict": "ok"}],
    })
    asked = []
    rep = AgentLoop(plan, {"scripted": be}, rd,
                    log=lambda *_: None).run(on_escalate=lambda e: asked.append(e) or {"action": "abort"})
    check("b1 被调用 2 次", be.calls.count("b1") == 2, str(be.calls))
    check("b2 也跑了", "b2" in be.calls, str(be.calls))
    check("未升级给 agent", not asked, f"{len(asked)} 次")


def case_C() -> None:
    print("\n[C] 升级改清单：SEMANTIC 失败 → agent 返回修订 plan → 重跑")
    plan, rd, _ = mkphase("C", [step("c1", backend="scripted"), step("c2")])
    be = ScriptedBackend({
        "c1": {"verdict": "mismatch", "failure_class": "SEMANTIC",
               "message": "界面不是预期", "diffs": ["ui_state 期望 terminal，实读 home"]},
    })
    asked = []

    def on_esc(esc):
        asked.append(esc)
        # agent 的"修改操作清单"：把 c1 换成修好的 c1fix
        return {"action": "plan", "plan": {
            "plan_id": "C", "rev": 2,
            "steps": [{"id": "c1fix", "backend": "scripted", "payload": {"task": "c1fix"}},
                      {"id": "c2", "backend": "scripted", "payload": {"task": "c2"}}]}}

    rep = AgentLoop(plan, {"scripted": be}, rd, log=lambda *_: None).run(on_escalate=on_esc)
    check("曾升级给 agent", len(asked) == 1, f"{len(asked)} 次")
    check("升级包带差异", bool(asked and asked[0].result.diffs), "")
    check("修订 plan 被落盘", os.path.exists(os.path.join(rd, "plan.json")), "")
    saved = json.load(open(os.path.join(rd, "plan.json"), encoding="utf-8"))
    check("落盘的是 rev2 清单", [s["id"] for s in saved["steps"]] == ["c1fix", "c2"],
          str([s["id"] for s in saved["steps"]]))
    check("报告 ok", rep["ok"], json.dumps(rep, ensure_ascii=False)[:120])


def case_D() -> None:
    print("\n[D] 终止：FATAL 失败 → 立即停并出报告")
    plan, rd, _ = mkphase("D", [step("d1"), step("d2")])
    be = ScriptedBackend({"d1": {"verdict": "error", "failure_class": "FATAL",
                                 "message": "TaskChainError"}})
    rep = AgentLoop(plan, {"scripted": be}, rd, log=lambda *_: None).run(
        on_escalate=lambda e: {"action": "abort"})
    check("d2 未执行", "d2" not in be.calls, str(be.calls))
    check("报告 ok=False", not rep["ok"], "")
    check("aborted_at=d1", rep["aborted_at"] == "d1", str(rep["aborted_at"]))


def case_E() -> None:
    print("\n[E] 干跑：NoopBackend 跑整份示例 plan")
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plan.example.json")
    plan = Plan.load(p)
    rd = tempfile.mkdtemp(prefix="guiops_E_")
    nb = NoopBackend(simulate_state="home")
    be = {"maa": nb, "prts": nb, "vision": nb, "noop": nb}
    rep = AgentLoop(plan, be, rd, log=lambda *_: None).run()
    check("示例 plan 步数=5", len(plan.steps) == 5, str(len(plan.steps)))
    check("状态文件有 5 行", sum(1 for _ in open(os.path.join(rd, "state.jsonl"),
                                                encoding="utf-8")) == 5, "")
    check("报告 ok", rep["ok"], json.dumps(rep, ensure_ascii=False)[:160])


def case_F() -> None:
    print("\n[F] 状态文件格式：每条都是合法 JSON 且含约定键")
    plan, rd, _ = mkphase("F", [step("f1")])
    AgentLoop(plan, {"scripted": ScriptedBackend({})}, rd, log=lambda *_: None).run()
    line = open(os.path.join(rd, "state.jsonl"), encoding="utf-8").readline()
    d = json.loads(line)
    need = {"step_id", "backend", "verdict", "failure_class", "duration_s", "expect",
            "observed", "events", "diffs", "message", "attempt", "plan_rev", "ok"}
    check("含全部约定键", need <= set(d), str(sorted(need - set(d))))


if __name__ == "__main__":
    for f in (case_A, case_B, case_C, case_D, case_E, case_F):
        f()
    print(f"\n=== selftest: {PASS} PASS / {FAIL} FAIL ===")
    raise SystemExit(1 if FAIL else 0)
