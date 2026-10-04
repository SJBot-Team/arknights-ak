# -*- coding: utf-8 -*-
"""prts_backend.py — 把 **prts+（赛博塑料）** 包装成可被 agent 驱动/监督的局内后端

## prts+ 的运行前提（✅ 已读源码 + 实测记录，见 knowledge/45 §七、53 §五）
1. 命令行：`prts+.exe --xlsm <ASCII路径> [--debug] [--autoenter]`
2. **路径必须纯 ASCII**（中文会被 PowerShell 传参打坏 ⇒ 本模块会先复制到 ASCII 暂存名）
3. 两种起法：
   - **局内起**（默认）：游戏**已在战斗中**，且**在第一秒内暂停**（它按费用条相对长度
     定位秒内帧 ⇒ 暂停越早，初始 tick 越准）。用 `--debug` 会输出 tick/action 日志。
   - **`--autoenter`**：局外自动进关（它只识别关卡内待部署区的干员，不认局外编队界面）
4. 时间口径：**1 秒 = 30 tick**（`GameTimeConfig.TICK_MAX_DEFAULT = 30`）。
5. 核心时序常量：`BULLET_THRESHOLD=15` / `FRAME_THRESHOLD=2` / `FRAME_WAITTIME=0.1`。

## ★ 已知致命限制：费用封顶 ⇒ 卡死（根因）
`analyze_time.py` 靠**费用条的填充长度**算"秒内相位(tick)"，`game_time` = 已完成秒数×30 + tick。
费用**封顶**（H12-4 上限 20）后费用条**不再填充** ⇒ tick 读数**停滞** ⇒
`while get_game_time() < target_time: 恢复 → sleep(0.1) → 暂停` 这个"逐帧推进"循环
**永不满足退出条件** ⇒ 停在那里，流程卡死。

**绕法（本模块实现"监控+重启"外围，内部绕法见 README）**：
- A. **不依赖 prts+ 的 tick**：用本工作区的费用尺相位时钟（`plugins/clock/frame_clock.py`）
  在**外部**算帧，封顶段用 `cost_timeline.py` 的锚点重算（已实现"跨越封顶"）。
- B. **把封顶段切成两段轴**：封顶前一段交给 prts+；封顶后一段由 agent 用"暂停 + 过帧"
  自己驱动（`paused_protocol.py`），不喂给 prts+。
- C. **监控 + 自动重启**：本模块 `watch()` 检测 stdout 中连续 N 秒无 `Performing action`
  且费用已达到轴表上限 ⇒ 判定"封顶卡死"，杀掉进程、按当前进度改轴表续跑。
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
import time

from contracts import Observation, OpStep, StepResult, classify_failure

PRTS_DEFAULT = r"D:\__soft\ak\prts+"
PRTS_EXE = "prts+.exe"

# prts+ 日志行的解析规则（来自对其运行输出的实测记录，见 apps/run_prts_compare.py）
LINE_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("initial_tick", re.compile(r"Setting initial tick to\s+(\d+)")),
    ("action", re.compile(r"Get action:\s*Action\((.*?)\)")),
    ("performing", re.compile(r"Performing action")),
    ("bullet", re.compile(r"Too much time, resuming and entering bullet time")),
    ("mismatch", re.compile(r"Game time mismatch")),
    ("game_time", re.compile(r"game time[:\s]+([\d.]+)")),
    ("threshold", re.compile(r"Set (bullet|frame) threshold to\s+([\d.]+)")),
    ("error", re.compile(r"(Error|Traceback|Exception|CRITICAL)", re.I)),
]


def to_ascii_path(src: str, scratch: str) -> str:
    """prts+ 的 `--xlsm` 有两个硬要求（都实测/源码级确认）：

    1. **必须纯 ASCII**（官方《首次使用指南》第 0 条：解压到没有中文/特殊字符的路径）；
    2. ★**必须是"规范化后的绝对路径"**——`src/excel.py::_connect()` 用
       `os.path.normpath(os.path.abspath(wb.FullName)) == self.file_path` 做等值比较，
       而 `main.py` 把命令行参数**原样**传入（不做 abspath）。
       传相对路径 / 大小写不一致 / 斜杠不一致 ⇒ 匹配失败 ⇒ **会再打开一份副本**，
       于是"宏的控制台（中转站页）"与"脚本操作的工作簿"不是同一个 ⇒ **"停止"按钮失效**。
       ⇒ 所以本函数一律 `normpath(abspath(...))`。
    """
    src = os.path.normpath(os.path.abspath(src))
    try:
        src.encode("ascii")
        return src
    except UnicodeEncodeError:
        pass
    os.makedirs(scratch, exist_ok=True)
    ext = os.path.splitext(src)[1] or ".xlsm"
    dst = os.path.normpath(os.path.abspath(
        os.path.join(scratch, f"axis_{abs(hash(src)) % (10 ** 8):08d}{ext}")))
    if not os.path.exists(dst) or os.path.getmtime(dst) < os.path.getmtime(src):
        shutil.copy2(src, dst)
    return dst


class PrtsBackend:
    """prts+ 局内后端。它**不是**步进式的：一旦启动就一直跑到轴表结束。
    所以本后端提供的"一步" = **启动一个受监督的会话并跑到某个里程碑**。
    """

    name = "prts"

    def __init__(self, prts_dir: str = PRTS_DEFAULT, scratch: str | None = None,
                 log=print):
        self.prts_dir = prts_dir
        self.exe = os.path.join(prts_dir, PRTS_EXE)
        self.scratch = scratch or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "_runtime")
        self.log = log
        self.proc: subprocess.Popen | None = None
        self.lines: list[dict] = []
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self.session_log = ""
        self.xlsm_path: str | None = None      # 规范化绝对路径（见 to_ascii_path）

    # ------------------------------------------------------------ 前提检查
    def preflight(self) -> dict:
        r = {"ok": False, "exe": os.path.exists(self.exe), "errors": []}
        if not r["exe"]:
            r["errors"].append(f"找不到 {self.exe}")
        try:
            import win32gui  # noqa: F401
            r["win32gui"] = True
        except Exception as e:                                   # noqa: BLE001
            r["win32gui"] = False
            r["errors"].append(f"缺 pywin32：{e!r}")
        r["ok"] = bool(r["exe"])
        return r

    # ------------------------------------------------------------ 启动会话
    def launch(self, xlsm: str, debug: bool = True, autoenter: bool = False,
               extra: list[str] | None = None) -> dict:
        """启动 prts+ 会话（非阻塞）。返回 {pid, cmd, xlsm}。"""
        xlsm_a = to_ascii_path(xlsm, os.path.join(self.scratch, "ascii"))
        self.xlsm_path = xlsm_a
        cmd = [self.exe, "--xlsm", xlsm_a]
        if debug:
            cmd.append("--debug")
        if autoenter:
            cmd.append("--autoenter")
        cmd += list(extra or [])
        os.makedirs(self.scratch, exist_ok=True)
        self.session_log = os.path.join(
            self.scratch, f"prts_{time.strftime('%Y%m%d_%H%M%S')}.jsonl")
        self.lines = []
        self._stop.clear()
        # prts+ 是 GUI 程序：stdout 不一定可读，所以**同时**写一份会话记录
        self.proc = subprocess.Popen(
            cmd, cwd=self.prts_dir, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, bufsize=1, text=True,
            encoding="utf-8", errors="replace")
        self._thread = threading.Thread(target=self._pump, daemon=True)
        self._thread.start()
        return {"pid": self.proc.pid, "cmd": cmd, "xlsm": xlsm_a, "session_log": self.session_log}

    def _pump(self) -> None:
        p = self.proc
        if p is None or p.stdout is None:
            return
        f = open(self.session_log, "a", encoding="utf-8")
        try:
            for raw in p.stdout:
                if self._stop.is_set():
                    break
                line = raw.rstrip("\n")
                rec = {"t": time.time(), "line": line}
                for kind, rx in LINE_PATTERNS:
                    m = rx.search(line)
                    if m:
                        rec["kind"] = kind
                        rec["match"] = m.groups()
                        break
                self.lines.append(rec)
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                f.flush()
        finally:
            f.close()

    def drain(self) -> list[dict]:
        out, self.lines = self.lines, []
        return out

    # ------------------------------------------------------------ 卡死检测
    def watch(self, stall_seconds: float = 20.0, cost_cap: int | None = None,
              cost_now_fn=None) -> dict:
        """★ 费用封顶卡死检测。
        判据：进程还活着，但 `Performing action` 已停 > stall_seconds；
              且（若给了 cost_cap/cost_now_fn）当前费用已达到或超过轴表上限。
        """
        t0 = time.time()
        last_action = t0
        seen_actions = 0
        while time.time() - t0 < stall_seconds * 3:
            if self.proc is None or self.proc.poll() is not None:
                return {"stalled": False, "exited": True,
                        "exit_code": None if self.proc is None else self.proc.returncode}
            for rec in self.drain():
                if rec.get("kind") == "performing":
                    last_action = rec["t"]
                    seen_actions += 1
            idle = time.time() - last_action
            cost = cost_now_fn() if cost_now_fn else None
            if seen_actions and idle > stall_seconds:
                capped = (cost_cap is None or cost is None or cost >= cost_cap)
                if capped:
                    return {"stalled": True, "idle_s": round(idle, 1),
                            "seen_actions": seen_actions, "cost": cost,
                            "cost_cap": cost_cap,
                            "reason": "费用封顶导致 tick 停滞（prts+ 已知限制）"}
                return {"stalled": True, "idle_s": round(idle, 1), "cost": cost,
                        "reason": "长时间无 action（可能轴表结束或卡在其他等待）"}
            time.sleep(0.5)
        return {"stalled": False, "timeout": True, "seen_actions": seen_actions}

    def kill(self) -> None:
        self._stop.set()
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.proc = None

    # ------------------------------------------------------------ 步进接口
    def step(self, op: OpStep) -> StepResult:
        """prts+ 的"一步"= 起一个受监督会话，跑到 (a) 进程自然结束、
        (b) 检测到封顶卡死、或 (c) op.timeout 到。"""
        sr = StepResult(step_id=op.id, backend=self.name, expect=op.expect)
        xlsm = op.payload.get("xlsm")
        if not xlsm or not os.path.exists(xlsm):
            sr.verdict, sr.message = "error", f"payload.xlsm 不存在：{xlsm}"
            sr.failure_class = "DATA"
            return sr.finish()
        info = self.launch(xlsm, debug=bool(op.payload.get("debug", True)),
                           autoenter=bool(op.payload.get("autoenter", False)),
                           extra=op.payload.get("extra"))
        sr.events.append({"t": time.time(), "name": "Launch", "details": info})
        cap = op.payload.get("cost_cap")
        stall = op.payload.get("stall_seconds", 20.0)
        deadline = time.time() + op.timeout
        w = {"stalled": False}
        while time.time() < deadline:
            if self.proc.poll() is not None:
                break
            if op.payload.get("watch_stall", True):
                w = self.watch(stall_seconds=stall, cost_cap=cap)
                if w.get("stalled"):
                    break
            time.sleep(0.5)
        rc = self.proc.poll() if self.proc else None
        all_recs = []
        for rec in self.drain():
            all_recs.append(rec)
        sr.events.extend(all_recs)
        sr.observed = self._digest(all_recs, rc, w)
        sr.evidence["session_log"] = self.session_log
        if w.get("stalled"):
            sr.verdict = "error"
            sr.message = w.get("reason", "会话停滞")
            sr.failure_class = "SEMANTIC" if "封顶" in sr.message else "TRANSIENT"
        elif rc is not None and rc != 0:
            sr.verdict = "error"
            sr.message = f"prts+ 退出码 {rc}"
            sr.failure_class = classify_failure("error", json.dumps(sr.observed)[:400])
        elif rc is None:
            sr.verdict, sr.message = "timeout", f"{op.timeout}s 未结束"
            sr.failure_class = "TRANSIENT"
        else:
            sr.verdict, sr.failure_class = "ok", "NONE"
        from maa_backend import compare
        sr.diffs = compare(sr.expect, sr.observed)
        if sr.diffs and sr.verdict == "ok":
            sr.verdict, sr.failure_class = "mismatch", "SEMANTIC"
            sr.message = "与预期不符：" + "；".join(sr.diffs)
        return sr.finish()

    def _digest(self, recs: list[dict], rc, w: dict) -> dict:
        acts, ticks = [], []
        for r in recs:
            if r.get("kind") == "action":
                acts.append(r.get("match"))
            elif r.get("kind") == "initial_tick":
                ticks.append(r.get("match"))
        return {"exit_code": rc, "n_actions": len(acts), "actions": acts[-40:],
                "initial_ticks": ticks, "stalled": w.get("stalled", False),
                "idle_s": w.get("idle_s"), "cost": w.get("cost"),
                "n_lines": len(recs)}

    def observe(self, shot_path: str | None = None) -> Observation:
        """回读 prts+ 的**状态面**（xlsm 的隐藏页「中转站」）+ 进程侧状态。

        ★ 控制/状态格（✅ 源码级确认，`src/excel.py`）：
           中转站!B1 = 状态；`is_paused()` 的实现就是 **B1 == '停止中'**
           中转站!B2 = 当前操作行号
           中转站!B3 = 错误日志（如 `错误：无法识别当前费用。`）
        ⇒ 这既是**读回进度/成败**的面，也是**写进去就能暂停 prts+** 的控制面。
        """
        ob = Observation()
        ob.extra = {"running": bool(self.proc and self.proc.poll() is not None
                                    and self.proc.poll() is None),
                    "pid": None if not self.proc else self.proc.pid,
                    "n_lines": len(self.lines)}
        st = self.read_status()
        if st:
            ob.extra.update(st)
            # 用状态机的语义填 ui_state，便于 AgentLoop 的 expect 比对
            ob.ui_state = {"运行中": "battle", "停止中": "paused",
                           "已停止": "post_battle"}.get(st.get("state"), "unknown")
        return ob

    # ------------------------------------------------------------ ★ 状态/控制面（xlsm）
    def read_status(self) -> dict | None:
        """读「中转站」的 B1/B2/B3。需要本机装有 Excel（prts+ 用的是 COM 自动化）。"""
        if not self.xlsm_path:
            return None
        try:
            import win32com.client as wc
            try:
                xl = wc.GetActiveObject("Excel.Application")
            except Exception:                                    # noqa: BLE001
                return None
            for wb in xl.Workbooks:
                if os.path.normpath(os.path.abspath(wb.FullName)) == self.xlsm_path:
                    sh = wb.Sheets("中转站")
                    return {"xlsm": self.xlsm_path,
                            "state": sh.Range("B1").Value,     # 运行中/停止中/已停止
                            "cur_row": sh.Range("B2").Value,   # 当前操作行
                            "err_log": sh.Range("B3").Value}   # 错误日志
            return None
        except Exception as e:                                   # noqa: BLE001
            return {"error": repr(e)}

    def request_pause(self) -> dict:
        """★ 写 `中转站!B1 = '停止中'` ⇒ prts+ 的两处 `while` 都会检查 `user_paused()` 而退出。
        这是官方"停止"按钮的等效操作（宏就是写这个格）。"""
        if not self.xlsm_path:
            return {"ok": False, "why": "未指定 xlsm"}
        try:
            import win32com.client as wc
            xl = wc.GetActiveObject("Excel.Application")
            for wb in xl.Workbooks:
                if os.path.normpath(os.path.abspath(wb.FullName)) == self.xlsm_path:
                    wb.Sheets("中转站").Range("B1").Value = "停止中"
                    return {"ok": True, "set": "中转站!B1 = 停止中"}
            return {"ok": False, "why": "未找到该工作簿（路径比较失败？见 to_ascii_path 注释）"}
        except Exception as e:                                   # noqa: BLE001
            return {"ok": False, "why": repr(e)}

    def read_progress(self) -> list[dict]:
        """读「作战记录」的 K 列「运行结果」与 A 列「当前执行」⇒ **逐行成败读回**。
        K 列是**单元格底色**（绿=成功 / 黄=延迟 / 红=失败），A 列是 `→` 指针。"""
        if not self.xlsm_path:
            return []
        try:
            import win32com.client as wc
            xl = wc.GetActiveObject("Excel.Application")
            for wb in xl.Workbooks:
                if os.path.normpath(os.path.abspath(wb.FullName)) != self.xlsm_path:
                    continue
                sh = wb.Sheets("作战记录")
                # ColorIndex 常见值：绿 4(亮绿) / 黄 6 / 红 3；用 RGB 更稳
                rows, cur = [], None
                for r in range(2, min(sh.UsedRange.Rows.Count + 1, 400)):
                    if (sh.Range(f"A{r}").Value or "").strip() == "→":
                        cur = r
                    k = sh.Range(f"K{r}")
                    rgb = None
                    try:
                        rgb = int(k.Interior.Color) & 0xFFFFFF
                    except Exception:                            # noqa: BLE001
                        pass
                    if k.Value or rgb:
                        rows.append({"row": r, "result_text": k.Value, "rgb": rgb})
                return rows
        except Exception:                                            # noqa: BLE001
            return []
        return []

    def abort(self) -> None:
        self.kill()
