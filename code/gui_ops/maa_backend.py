# -*- coding: utf-8 -*-
"""maa_backend.py — 用 **MaaCore.dll 的 C API** 把 MAA 变成可**步进驱动**的执行器

## 为什么能步进（结论，✅ 实测）
MaaCore.dll 暴露 30 个 `Asst*` 函数（PE 导出表已核）。关键四个：

| 函数 | 作用 | 对 agent 的意义 |
|---|---|---|
| `AsstAppendTask(h, type, params)` -> task_id | 把**一个**任务排队 | **下达一步** |
| `AsstStart(h)` | 开始跑队列 | 启动 |
| `AsstCreateEx(cb, arg)` | 注册回调（msg, details_json, arg） | **读回结果**（结构化 JSON） |
| `AsstGetImage(h, buf, n)` | 取当前截图 | **观察** |

⇒ **步进的粒度 = 一个 MAA 任务链**：每次只 append 一个任务、`AsstStart`、
等该 chain 的 `TaskChainCompleted/Error` 回调（msg 10002/10000）就返回。
链**内部**不可单步（MaaCore 自己跑 ProcessTask 循环），但链内每一步都会以
`SubTaskStart/Completed`（20001/20002）回调出来，可当**过程遥测**用。

## 正确调用顺序（✅ 实测，顺序错会返回空句柄）
    AsstSetUserDir(userdir)      # 日志/调试输出目录（建议指向工作区，别污染 MAA 安装目录）
    AsstLoadResource(MAA_ROOT)   # ★ 参数是 **MAA 根目录**（其下有 resource/），不是 resource/ 本身
    AsstCreateEx(cb, None)       # -> handle
    ... AsstAppendTask / AsstStart / AsstGetImage ...
    AsstDestroy(handle)

## 三种连接方式
- ADB：`AsstAsyncConnect(h, adb_path, address, config_json, block=True)`
- Win32 窗口：`AsstAsyncAttachWindow(h, hwnd, screencap, mouse, keyboard, block=True)`
  ⇒ 无需 ADB。screencap/mouse/keyboard 枚举见 AsstCaller.h（本模块已抄录）
- 不连接：只能验证接口链路（`AsstStart` 会回 `ConnectionInfo{what:ScreencapFailed}`）

## 安全边界（本机用户要求）
- **不** login：绝不 append `StartUp` 的登录相关分支，也不点账号管理；
- 默认 `--dry-run`：只 preflight + observe，不 append 任务。
"""
from __future__ import annotations

import ctypes
import json
import os
import threading
import time
from dataclasses import dataclass, field

from contracts import Observation, OpStep, StepResult, classify_failure

# ---- AsstMsg 枚举（抄自 src/MaaCore/Common/AsstMsg.h）----
MSG = {
    0: "InternalError", 1: "InitFailed", 2: "ConnectionInfo", 3: "AllTasksCompleted",
    4: "AsyncCallInfo", 5: "Destroyed",
    10000: "TaskChainError", 10001: "TaskChainStart", 10002: "TaskChainCompleted",
    10003: "TaskChainExtraInfo", 10004: "TaskChainStopped",
    20000: "SubTaskError", 20001: "SubTaskStart", 20002: "SubTaskCompleted",
    20003: "SubTaskExtraInfo", 20004: "SubTaskStopped",
    30000: "ReportRequest",
}
MSG_ID = {v: k for k, v in MSG.items()}

# ---- Win32 截图/输入方式（抄自 include/AsstCaller.h）----
SCREENCAP = {"None": 0, "GDI": 1, "FramePool": 2, "DXGI_DesktopDup": 4,
             "DXGI_DesktopDup_Window": 8, "PrintWindow": 16, "ScreenDC": 32}
INPUT_METHOD = {"None": 0, "Seize": 1, "SendMessage": 2, "PostMessage": 4,
                "LegacyEvent": 8, "PostThreadMessage": 16,
                "SendMessageWithCursorPos": 32, "PostMessageWithCursorPos": 64,
                "SendMessageWithWindowPos": 128, "PostMessageWithWindowPos": 256}

# ---- InstanceOptionKey（实测：3=DeploymentWithPause 可设；2 触控模式只在已连接时可用）----
OPT = {"Invalid": 0, "TouchMode": 2, "DeploymentWithPause": 3,
       "AdbLiteEnabled": 4, "KillAdbOnExit": 5}

MAA_ROOT_DEFAULT = r"D:\__soft\MAA"


class MaaBackend:
    """MAA 步进后端。一个实例 = 一个 MaaCore 句柄。"""

    name = "maa"

    def __init__(self, maa_root: str = MAA_ROOT_DEFAULT, user_dir: str | None = None,
                 log=print):
        self.maa_root = maa_root
        self.user_dir = user_dir or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "_runtime", "maa_userdir")
        self.log = log
        self.dll = None
        self.h = None
        self._cb = None                       # 必须保引用，否则回调被 GC → 崩溃
        self.events: list[dict] = []
        self._lock = threading.Lock()
        self.connected = False
        self.conn_info: dict = {}

    # ------------------------------------------------------------ 加载
    def preflight(self) -> dict:
        r = {"ok": False, "dll": None, "resource": None, "version": None, "errors": []}
        try:
            os.makedirs(self.user_dir, exist_ok=True)
            os.add_dll_directory(self.maa_root)
            os.environ["PATH"] = self.maa_root + os.pathsep + os.environ.get("PATH", "")
            self.dll = ctypes.CDLL(os.path.join(self.maa_root, "MaaCore.dll"))
        except Exception as e:                                  # noqa: BLE001
            r["errors"].append(f"加载 MaaCore.dll 失败: {e!r}")
            return r
        d = self.dll
        d.AsstGetVersion.restype = ctypes.c_char_p
        d.AsstSetUserDir.argtypes = [ctypes.c_char_p]; d.AsstSetUserDir.restype = ctypes.c_ubyte
        d.AsstLoadResource.argtypes = [ctypes.c_char_p]; d.AsstLoadResource.restype = ctypes.c_ubyte
        d.AsstSetStaticOption.argtypes = [ctypes.c_int32, ctypes.c_char_p]
        d.AsstSetStaticOption.restype = ctypes.c_ubyte
        r["version"] = d.AsstGetVersion().decode()
        r["dll"] = True
        r["user_dir_set"] = bool(d.AsstSetUserDir(self.user_dir.encode()))
        # ★ 传 MAA 根目录（其下有 resource/）
        r["resource"] = bool(d.AsstLoadResource(self.maa_root.encode()))
        r["ok"] = bool(r["resource"])
        if not r["ok"]:
            r["errors"].append("AsstLoadResource 返回 0：路径应为含 resource/ 的 MAA 根目录")
        return r

    def open(self) -> None:
        if self.dll is None:
            raise RuntimeError("先调用 preflight()")
        d = self.dll
        self._CB = ctypes.CFUNCTYPE(None, ctypes.c_int32, ctypes.c_char_p, ctypes.c_void_p)
        d.AsstCreateEx.restype = ctypes.c_void_p
        d.AsstCreateEx.argtypes = [self._CB, ctypes.c_void_p]
        d.AsstSetInstanceOption.argtypes = [ctypes.c_void_p, ctypes.c_int32, ctypes.c_char_p]
        d.AsstSetInstanceOption.restype = ctypes.c_ubyte
        d.AsstAppendTask.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p]
        d.AsstAppendTask.restype = ctypes.c_int32
        d.AsstStart.argtypes = [ctypes.c_void_p]; d.AsstStart.restype = ctypes.c_ubyte
        d.AsstStop.argtypes = [ctypes.c_void_p]; d.AsstStop.restype = ctypes.c_ubyte
        d.AsstRunning.argtypes = [ctypes.c_void_p]; d.AsstRunning.restype = ctypes.c_ubyte
        d.AsstConnected.argtypes = [ctypes.c_void_p]; d.AsstConnected.restype = ctypes.c_ubyte
        d.AsstGetImage.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint64]
        d.AsstGetImage.restype = ctypes.c_uint64
        d.AsstAsyncConnect.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p,
                                       ctypes.c_char_p, ctypes.c_ubyte]
        d.AsstAsyncConnect.restype = ctypes.c_int32
        d.AsstAsyncAttachWindow.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint64,
                                            ctypes.c_uint64, ctypes.c_uint64, ctypes.c_ubyte]
        d.AsstAsyncAttachWindow.restype = ctypes.c_int32
        d.AsstAsyncScreencap.argtypes = [ctypes.c_void_p, ctypes.c_ubyte]
        d.AsstAsyncScreencap.restype = ctypes.c_int32
        d.AsstAsyncClick.argtypes = [ctypes.c_void_p, ctypes.c_int32, ctypes.c_int32,
                                     ctypes.c_ubyte]
        d.AsstAsyncClick.restype = ctypes.c_int32
        d.AsstDestroy.argtypes = [ctypes.c_void_p]

        @self._CB
        def _cb(msg, details, arg):                              # noqa: ANN001
            try:
                d = json.loads(details.decode("utf-8", "replace")) if details else {}
            except Exception:                                    # noqa: BLE001
                d = {"_raw": (details or b"").decode("utf-8", "replace")}
            with self._lock:
                self.events.append({"t": time.time(), "msg": int(msg),
                                    "name": MSG.get(int(msg), str(msg)), "details": d})

        # ★★ 必须**同时**保活回调实例本身：只存 CFUNCTYPE 类型不够，
        #    实例被 GC 后 MaaCore 会调到已释放的 trampoline ⇒
        #    `OSError: exception: single step`（本项目实测踩过）。
        self._callback = _cb
        self.h = d.AsstCreateEx(self._callback, None)
        if not self.h:
            raise RuntimeError("AsstCreateEx 返回空句柄")
        d.AsstSetInstanceOption(self.h, OPT["DeploymentWithPause"], b"1")
        d.AsstSetInstanceOption(self.h, OPT["KillAdbOnExit"], b"1")

    def close(self) -> None:
        if self.h and self.dll:
            self.dll.AsstDestroy(self.h)
            self.h = None

    # ------------------------------------------------------------ 连接
    def connect_adb(self, adb_path: str, address: str, config: str = "General",
                    timeout: float = 60.0) -> bool:
        """MAA 的通用 ADB 通道（minitouch 点击、adb screencap 截图）。"""
        self.dll.AsstAsyncConnect(self.h, adb_path.encode(), address.encode(),
                                  config.encode(), 1)
        return self._wait_connected(timeout)

    def attach_window(self, hwnd: int, screencap: str = "PrintWindow",
                      mouse: str = "SendMessage", keyboard: str = "SendMessage",
                      timeout: float = 60.0) -> bool:
        """★ Win32 直连窗口：无需 ADB。目标窗口实测应为渲染子窗口（MuMu 的 nemuwin/MuMuPlayer）。"""
        self.dll.AsstAsyncAttachWindow(self.h, ctypes.c_void_p(int(hwnd)),
                                       SCREENCAP[screencap], INPUT_METHOD[mouse],
                                       INPUT_METHOD[keyboard], 1)
        return self._wait_connected(timeout)

    def _wait_connected(self, timeout: float) -> bool:
        t0 = time.time()
        while time.time() - t0 < timeout:
            if self.dll.AsstConnected(self.h):
                self.connected = True
                return True
            for e in self.drain():
                if e["name"] == "ConnectionInfo":
                    self.conn_info = e["details"]
            time.sleep(0.3)
        self.connected = False
        return False

    # ------------------------------------------------------------ 事件流
    def drain(self) -> list[dict]:
        with self._lock:
            ev, self.events = self.events, []
        return ev

    def _wait_chain(self, task_id: int, timeout: float) -> tuple[str, list[dict], str]:
        """等某个 taskchain 结束。返回 (终态名, 该链的事件, 失败原因)。"""
        collected: list[dict] = []
        t0 = time.time()
        while time.time() - t0 < timeout:
            for e in self.drain():
                collected.append(e)
                det = e["details"] or {}
                if det.get("taskid") not in (task_id, 0, None) and \
                        det.get("taskchain") is None:
                    continue
                if e["name"] == "TaskChainCompleted" and det.get("taskid") == task_id:
                    return "completed", collected, ""
                if e["name"] in ("TaskChainError", "TaskChainStopped") and \
                        det.get("taskid") == task_id:
                    return ("error" if e["name"] == "TaskChainError" else "stopped",
                            collected, json.dumps(det, ensure_ascii=False))
                if e["name"] == "AllTasksCompleted":
                    return "completed", collected, ""
                if e["name"] in ("InternalError", "InitFailed"):
                    return "error", collected, json.dumps(det, ensure_ascii=False)
                if e["name"] == "ConnectionInfo":
                    return "error", collected, json.dumps(det, ensure_ascii=False)
            time.sleep(0.15)
        return "timeout", collected, f"{timeout}s 内未收到该任务链终态"

    # ------------------------------------------------------------ 观察
    def observe(self, shot_path: str | None = None, with_ui: bool = True) -> Observation:
        """读回当前画面 +（可选）界面语义。AsstGetImage 返回 PNG 字节。"""
        ob = Observation()
        n = self.dll.AsstGetImage(self.h, None, 0)
        SIZE_MAX = (1 << 64) - 1
        if n in (0, SIZE_MAX):
            ob.extra["image_error"] = "AsstGetImage 无可用画面（未连接或截图失败）"
            return ob
        buf = ctypes.create_string_buffer(int(n))
        n2 = self.dll.AsstGetImage(self.h, buf, int(n))
        data = buf.raw[:int(n2)]
        ob.extra["png_bytes"] = len(data)
        if shot_path:
            os.makedirs(os.path.dirname(os.path.abspath(shot_path)), exist_ok=True)
            with open(shot_path, "wb") as f:
                f.write(data)
            ob.shot = shot_path
        if with_ui and data:
            try:
                import cv2
                import numpy as np
                img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
                ob.extra["shape"] = list(img.shape) if img is not None else None
                if img is not None:
                    st = _classify_ui(img)
                    ob.ui_state = st
            except Exception as e:                               # noqa: BLE001
                ob.extra["decode_error"] = repr(e)
        return ob

    # ------------------------------------------------------------ 步进
    def step(self, op: OpStep) -> StepResult:
        """执行**一个** MAA 任务链并读回结果。这是 agent 闭环的"一步"。"""
        sr = StepResult(step_id=op.id, backend=self.name, expect=op.expect)
        task_type = op.payload.get("task")
        if not task_type:
            sr.verdict, sr.message = "error", "payload 缺 task（MAA 任务类型）"
            sr.failure_class = "DATA"
            return sr.finish()
        params = {k: v for k, v in op.payload.items() if k != "task"}
        self.drain()
        tid = self.dll.AsstAppendTask(self.h, str(task_type).encode(),
                                     json.dumps(params, ensure_ascii=False).encode())
        sr.events.append({"t": time.time(), "name": "AppendTask",
                          "details": {"task": task_type, "params": params, "task_id": tid}})
        if tid < 0:
            sr.verdict, sr.message = "error", f"AsstAppendTask 被拒（返回 {tid}）：参数不合法"
            sr.failure_class = "DATA"
            return sr.finish()
        if not self.dll.AsstStart(self.h):
            sr.verdict, sr.message = "error", "AsstStart 返回 0"
            sr.failure_class = "FATAL"
            return sr.finish()
        state, ev, why = self._wait_chain(int(tid), op.timeout)
        sr.events.extend(ev)
        sr.observed = self._digest(ev, task_type)
        if state == "completed":
            sr.verdict = "ok"
            sr.failure_class = "NONE"
        elif state == "timeout":
            sr.verdict, sr.message = "timeout", why
            sr.failure_class = classify_failure("timeout", why)
        elif state == "stopped":
            sr.verdict, sr.message = "error", "任务链被停止（AsstStop）"
            sr.failure_class = "FATAL"
        else:
            sr.verdict, sr.message = "error", why or "任务链报错"
            sr.failure_class = classify_failure("error", why)
        # 用 expect 比对（有 expect 才能升级为 mismatch）
        diffs = compare(sr.expect, sr.observed)
        sr.diffs = diffs
        if diffs and sr.verdict == "ok":
            sr.verdict = "mismatch"
            sr.failure_class = "SEMANTIC"
            sr.message = "识别/执行成功但状态与预期不符：" + "；".join(diffs)
        return sr.finish()

    def _digest(self, ev: list[dict], task_type: str) -> dict:
        """把事件流压成可判定的摘要：识别结果、动作、候选链、命中分数。"""
        subs, to_be, scores = [], [], []
        for e in ev:
            det = e.get("details") or {}
            if e["name"] in ("SubTaskCompleted", "SubTaskStart"):
                d = det.get("details") or {}
                subs.append({"task": d.get("task"), "algorithm": d.get("algorithm"),
                             "action": d.get("action"), "exec_times": d.get("exec_times"),
                             "score": (d.get("result") or {}).get("score")})
                if (d.get("result") or {}).get("score") is not None:
                    scores.append(d["result"]["score"])
            elif "to_be_recognized" in det:
                to_be.append({"to_be_recognized": det.get("to_be_recognized"),
                              "cur_retry": det.get("cur_retry"),
                              "retry_times": det.get("retry_times")})
        return {"task": task_type, "subtasks": subs[-40:], "recognize_rounds": to_be[-20:],
                "max_score": max(scores) if scores else None,
                "n_subtasks": len(subs)}

    def abort(self) -> None:
        if self.h:
            self.dll.AsstStop(self.h)

    # ----------------------------------------------------------- ★ 原生步进：SingleStep
    # MAA 有一个**官方单步任务** `SingleStep`（目前仅支持战斗 / copilot）。
    # subtype: "stage"（设关卡）/ "start"（开始作战）/ "action"（单步操作）
    #
    # ★★ 血坑（✅ 实测）：官方文档的 action 示例是**错的**。
    #   SingleStepTask::append_copilot_action 把 details 直接交给
    #   CopilotConfig::parse_actions，后者第一行是 json.at("actions") ⇒
    #   details **必须**是 {"actions": [ <单个 action> ]}；
    #   传裸 action 对象会让 AsstAppendTask 返回 0（失败），报错只在 asst.log 里：
    #     [ERR] asst::SingleStepTask::append_copilot_action invalid map<K, T> key
    def ss_stage(self, stage_name: str) -> int:
        return self._append("SingleStep", {"type": "copilot", "subtype": "stage",
                                           "details": {"stage_name": stage_name}})

    def ss_start(self) -> int:
        return self._append("SingleStep", {"type": "copilot", "subtype": "start"})

    def ss_action(self, action: dict) -> int:
        """单步执行**一个**战斗 action（部署/技能/撤退/二倍速/点击…）。"""
        return self._append("SingleStep", {"type": "copilot", "subtype": "action",
                                           "details": {"actions": [action]}})

    def _append(self, task_type: str, params: dict) -> int:
        return int(self.dll.AsstAppendTask(
            self.h, task_type.encode(), json.dumps(params, ensure_ascii=False).encode()))

    def step_single(self, op: OpStep) -> StepResult:
        """★ 真正的"一步"：用 SingleStep 执行 payload.action 里的**一个**战斗操作。

        这是最贴近 agent 闭环的粒度：一次调用 = 一个部署/一次技能。
        """
        act = op.payload.get("action")
        if not isinstance(act, dict):
            sr = StepResult(step_id=op.id, backend=self.name, verdict="error",
                            failure_class="DATA", message="payload.action 必须是单个 action 对象")
            return sr.finish()
        sr = StepResult(step_id=op.id, backend=self.name, expect=op.expect)
        self.drain()
        tid = self.ss_action(act)
        sr.events.append({"t": time.time(), "name": "AppendTask",
                          "details": {"SingleStep": act, "task_id": tid}})
        if tid < 0:
            # 注意：本平台实测失败时返回 0；0 也是失败
            sr.verdict = "error"
            sr.failure_class = "DATA"
            sr.message = (f"AsstAppendTask('SingleStep') 被拒（{tid}）——"
                          "检查 details 是否包在 actions 数组里")
            return sr.finish()
        if not self.dll.AsstStart(self.h):
            sr.verdict, sr.failure_class, sr.message = "error", "FATAL", "AsstStart 返回 0"
            return sr.finish()
        state, ev, why = self._wait_chain(int(tid), op.timeout)
        sr.events.extend(ev)
        sr.observed = self._digest(ev, "SingleStep")
        sr.observed["action"] = act
        sr.verdict = "ok" if state == "completed" else (
            "timeout" if state == "timeout" else "error")
        sr.failure_class = ("NONE" if sr.verdict == "ok"
                            else classify_failure(sr.verdict, why))
        if sr.verdict != "ok":
            sr.message = why or f"单步未完成（{state}）"
        from maa_backend import compare as _cmp
        sr.diffs = _cmp(sr.expect, sr.observed)
        if sr.diffs and sr.verdict == "ok":
            sr.verdict, sr.failure_class = "mismatch", "SEMANTIC"
            sr.message = "与预期不符：" + "；".join(sr.diffs)
        return sr.finish()

    # ----------------------------------------------------------- 窄接口（agent 直接操纵）
    def click(self, x: int, y: int, block: bool = True) -> int:
        """★ 只点一下（1280×720 基准坐标？不——这里用**设备物理坐标**，MAA 内部会换算）。"""
        return self.dll.AsstAsyncClick(self.h, int(x), int(y), 1 if block else 0)

    def screencap(self, block: bool = True) -> int:
        return self.dll.AsstAsyncScreencap(self.h, 1 if block else 0)


# ---------------------------------------------------------------- 界面语义
_UI = None


def _classify_ui(img) -> str:
    """用工作区既有 vision 插件判界面语义；不可用则退回 'unknown'。"""
    global _UI
    try:
        if _UI is None:
            import sys
            vis = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                               "vision")
            if vis not in sys.path:
                sys.path.insert(0, vis)
            from plugins.recognize.ui_state import UiState  # type: ignore
            _UI = UiState()
        return _UI.classify(img)["state"]
    except Exception:                                            # noqa: BLE001
        return "unknown"


# ---------------------------------------------------------------- 预期比对
def compare(expect: dict, observed: dict | Observation) -> list[str]:
    """通用"预期 vs 实读"比对。expect 的键分两类：
    - `ui_state` / `cost` / `cost_min` / `cost_max` / `frame_now`  → 直接比
    - `task` / `max_score_min` / `subtask_seen`                    → 比 MAA 摘要
    返回差异列表（空 = 全部符合）。
    """
    obs = observed.to_dict() if isinstance(observed, Observation) else dict(observed)
    out: list[str] = []
    for k, want in (expect or {}).items():
        if k == "ui_state":
            if obs.get("ui_state") not in (want if isinstance(want, list) else [want]):
                out.append(f"ui_state 期望 {want}，实读 {obs.get('ui_state')}")
        elif k == "ui_state_in":
            if obs.get("ui_state") not in want:
                out.append(f"ui_state 期望属于 {want}，实读 {obs.get('ui_state')}")
        elif k == "cost":
            if obs.get("cost") != want:
                out.append(f"cost 期望 {want}，实读 {obs.get('cost')}")
        elif k == "cost_min" and (obs.get("cost") is None or obs["cost"] < want):
            out.append(f"cost 期望 >= {want}，实读 {obs.get('cost')}")
        elif k == "cost_max" and (obs.get("cost") is None or obs["cost"] > want):
            out.append(f"cost 期望 <= {want}，实读 {obs.get('cost')}")
        elif k == "frame_min" and (obs.get("frame_now") is None or obs["frame_now"] < want):
            out.append(f"frame 期望 >= {want}，实读 {obs.get('frame_now')}")
        elif k == "cost_delta_ge":
            d = obs.get("cost_delta")
            if d is None or d < want:
                out.append(f"费用扣减期望 >= {want}，实读 {d}")
        elif k == "max_score_min":
            s = obs.get("max_score")
            if s is None or s < want:
                out.append(f"模板最高分期望 >= {want}，实读 {s}")
        elif k == "task":
            if obs.get("task") != want:
                out.append(f"任务期望 {want}，实读 {obs.get('task')}")
        elif k == "subtask_seen":
            seen = {s["task"] for s in obs.get("subtasks", []) if s.get("task")}
            missing = [t for t in want if t not in seen]
            if missing:
                out.append(f"未观察到子任务 {missing}")
        elif k == "exit_code" and obs.get("exit_code") != want:
            out.append(f"退出码期望 {want}，实读 {obs.get('exit_code')}")
    return out
