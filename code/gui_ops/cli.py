# -*- coding: utf-8 -*-
"""cli.py — gui_ops 的统一入口

    python cli.py preflight                    # 检查 MAA / prts+ 前提（只读，不碰游戏）
    python cli.py maa-probe                    # ★ 证明 MaaCore 绑定 + 回调读回可用
    python cli.py maa-tasks                    # 列出 MaaCore 支持的任务类型与参数要点
    python cli.py run --plan plan.example.json --dry-run        # 空跑整份清单（不注入输入）
    python cli.py run --plan plan.example.json --backend maa --connect-adb ...
    python cli.py logs --run-dir _runs/<id>    # 读 state.jsonl 出报告
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8")

from agent_loop import AgentLoop                                    # noqa: E402
from contracts import Plan                                          # noqa: E402
from noop_backend import NoopBackend                                # noqa: E402
from prts_backend import PrtsBackend                                # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def _run_dir(tag: str) -> str:
    d = os.path.join(HERE, "_runs", f"{tag}_{time.strftime('%Y%m%d_%H%M%S')}")
    os.makedirs(d, exist_ok=True)
    return d


def cmd_preflight(a) -> int:
    out = {}
    try:
        from maa_backend import MaaBackend
        be = MaaBackend(a.maa_root)
        out["maa"] = be.preflight()
    except Exception as e:                                          # noqa: BLE001
        out["maa"] = {"ok": False, "errors": [repr(e)]}
    pb = PrtsBackend(a.prts_dir)
    out["prts"] = pb.preflight()
    try:
        import win32gui                                             # noqa: F401
        hwnd = win32gui.FindWindow(None, "MuMu模拟器12")
        out["emulator"] = {"window_found": bool(hwnd), "hwnd": hwnd}
    except Exception as e:                                          # noqa: BLE001
        out["emulator"] = {"error": repr(e)}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out["maa"].get("ok") and out["prts"].get("ok") else 1


def cmd_maa_probe(a) -> int:
    """★ 只验证接口链路：LoadResource → Create → AppendTask → 回调读回。
    **不连接设备、不启动任务**（AsstStart 只在 --start 时调用）。"""
    from maa_backend import MaaBackend, MSG
    be = MaaBackend(a.maa_root)
    pf = be.preflight()
    print("preflight:", json.dumps(pf, ensure_ascii=False))
    if not pf.get("ok"):
        return 1
    be.open()
    print("handle:", hex(be.h))
    tid = be.dll.AsstAppendTask(be.h, b"StartUp",
                                b'{"client_type":"Official","start_game_enabled":false}')
    print("AsstAppendTask('StartUp') -> task_id =", tid, "（>=0 = 接口接受）")
    be.dll.AsstSetInstanceOption(be.h, 3, b"1")
    print("DeploymentWithPause 已设（= MAA 的 BattleDeployWhenPause）")
    if a.start:
        print("AsstStart ->", be.dll.AsstStart(be.h), "（未连接设备，预期回调 ConnectionInfo/ScreencapFailed）")
        time.sleep(3)
    else:
        print("（未调用 AsstStart；加 --start 可验证错误回调通道）")
    ev = be.drain()
    print(f"回调事件 {len(ev)} 条：")
    for e in ev[:20]:
        print(f"  msg={e['msg']:<6} {e['name']:<20} {json.dumps(e['details'], ensure_ascii=False)[:200]}")
    be.close()
    return 0


def cmd_maa_singlestep(a) -> int:
    """★ 验证 MAA 的**原生单步**接口 SingleStep。
    对照实验：裸 action（官方文档写法，错）vs 包在 actions 数组里（对）。
    不连接设备也能看出 AsstAppendTask 的返回码差异（0 = 被拒）。"""
    from maa_backend import MaaBackend
    be = MaaBackend(a.maa_root)
    pf = be.preflight()
    print("preflight:", json.dumps(pf, ensure_ascii=False))
    if not pf.get("ok"):
        return 1
    be.open()
    act = {"type": "Deploy", "name": "测试", "location": [5, 3], "direction": "Right"}
    print("\n【对照实验】AsstAppendTask('SingleStep', subtype='action')")
    t_bad = be.dll.AsstAppendTask(
        be.h, b"SingleStep",
        json.dumps({"type": "copilot", "subtype": "action", "details": act}).encode())
    print(f"  裸 action（官方文档写法，错）  -> task_id = {t_bad}   （0 = 被拒）")
    t_ok = be.ss_action(act)
    print(f"  包在 actions 数组里（正确）    -> task_id = {t_ok}   （>0 = 接受）")
    t_stage = be.ss_stage("1-7")
    print(f"  subtype='stage' 设关卡 1-7    -> task_id = {t_stage}")
    t_start = be.ss_start()
    print(f"  subtype='start' 开始作战       -> task_id = {t_start}")
    print("\n源码级判据：SingleStepTask::append_copilot_action 把 details 交给")
    print("  CopilotConfig::parse_actions，后者第一行是 json.at(\"actions\")")
    print("  ⇒ details 必须是 {\"actions\": [<单个 action>]}")
    be.close()
    return 0 if (t_bad <= 0 <= t_ok) else 3


def cmd_maa_tasks(a) -> int:
    """从 resource/tasks/tasks.json 里读出 MAA 支持的任务链入口与常用参数。"""
    p = os.path.join(a.maa_root, "resource", "tasks", "tasks.json")
    import re
    raw = open(p, encoding="utf-8").read()
    d = json.loads(re.sub(r"^\s*//.*$", "", raw, flags=re.M))
    if a.grep:
        for k in sorted(d):
            if a.grep.lower() in k.lower():
                print(f"{k}: {json.dumps(d[k], ensure_ascii=False)[:300]}")
    else:
        print(f"tasks.json 任务总数：{len(d)}")
        print("（用 --grep <关键字> 过滤，例如 --grep BattleDeploy）")
    return 0


def cmd_run(a) -> int:
    plan = Plan.load(a.plan)
    rd = a.run_dir or _run_dir(plan.plan_id)
    backends: dict = {}
    if a.dry_run:
        backends["maa"] = NoopBackend(simulate_state=a.sim_state)
        backends["prts"] = NoopBackend(simulate_state=a.sim_state)
        backends["vision"] = NoopBackend(simulate_state="battle")
        backends["noop"] = backends["maa"]
        print("[模式] DRY-RUN：不连接游戏、不注入任何输入")
    else:
        from maa_backend import MaaBackend
        mb = MaaBackend(a.maa_root)
        pf = mb.preflight()
        if not pf.get("ok"):
            print("[错误] MAA 前提不满足：", pf); return 2
        mb.open()
        if a.connect_adb:
            adb, addr = a.connect_adb.split(",", 1)
            print("[连接] ADB", adb, addr, "→", mb.connect_adb(adb, addr))
        elif a.attach_hwnd:
            print("[连接] Win32 hwnd", a.attach_hwnd, "→",
                  mb.attach_window(int(a.attach_hwnd, 0)))
        else:
            print("[警告] 未指定 --connect-adb / --attach-hwnd，MAA 只能做接口链路测试")
        backends["maa"] = mb
        backends["prts"] = PrtsBackend(a.prts_dir)
    def on_escalate(esc):
        print("\n" + "=" * 70)
        print(esc.text())
        print("=" * 70)
        if a.auto == "retry":
            return {"action": "retry"}
        if a.auto == "skip":
            return {"action": "skip"}
        if a.auto == "abort" or not sys.stdin.isatty():
            return {"action": "abort"}
        try:
            c = input("处置 [r]etry/[s]kip/[a]bort/[p]lan(读同目录 plan.fix.json): ").strip().lower()
        except EOFError:
            return {"action": "abort"}
        if c.startswith("r"):
            return {"action": "retry"}
        if c.startswith("s"):
            return {"action": "skip"}
        if c.startswith("p"):
            fp = os.path.join(rd, "plan.fix.json")
            if os.path.exists(fp):
                return {"action": "plan", "plan": json.load(open(fp, encoding="utf-8"))}
            print("  没有", fp)
        return {"action": "abort"}

    loop = AgentLoop(plan, backends, rd, log=print)
    try:
        rep = loop.run(on_escalate=on_escalate)
    finally:
        loop.close()
    print("\n=== 运行报告 ===")
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    print(f"状态文件: {os.path.join(rd, 'state.jsonl')}")
    return 0 if rep["ok"] else 3


def cmd_logs(a) -> int:
    p = os.path.join(a.run_dir, "state.jsonl")
    if not os.path.exists(p):
        print("没有", p); return 1
    n = ok = 0
    for line in open(p, encoding="utf-8"):
        d = json.loads(line)
        n += 1
        if d.get("ok"):
            ok += 1
        print(f"  #{n:<3} plan_rev={d.get('plan_rev')} attempt={d.get('attempt')} "
              f"{d['step_id']:<16} {d['verdict']:<9} {d['failure_class']:<10} "
              f"{d.get('duration_s')}s  {d.get('message','')[:70]}")
    print(f"\n共 {n} 条记录，成功 {ok}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="gui_ops")
    ap.add_argument("--maa-root", default=r"D:\__soft\MAA")
    ap.add_argument("--prts-dir", default=r"D:\__soft\ak\prts+")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("preflight").set_defaults(fn=cmd_preflight)

    p = sub.add_parser("maa-probe"); p.add_argument("--start", action="store_true")
    p.set_defaults(fn=cmd_maa_probe)

    sub.add_parser("maa-singlestep").set_defaults(fn=cmd_maa_singlestep)

    p = sub.add_parser("maa-tasks"); p.add_argument("--grep", default=None)
    p.set_defaults(fn=cmd_maa_tasks)

    p = sub.add_parser("run")
    p.add_argument("--plan", default=os.path.join(HERE, "plan.example.json"))
    p.add_argument("--run-dir", default=None)
    p.add_argument("--dry-run", action="store_true", default=False)
    p.add_argument("--connect-adb", default=None, help="adb路径,地址 如 D:\\...\\adb.exe,127.0.0.1:16384")
    p.add_argument("--attach-hwnd", default=None, help="Win32 窗口句柄（十进制或 0x 十六进制）")
    p.add_argument("--auto", choices=["retry", "skip", "abort"], default="abort",
                   help="非交互时对 escalate 的默认处置")
    p.add_argument("--sim-state", default="unknown", help="dry-run 时模拟的界面语义")
    p.set_defaults(fn=cmd_run)

    p = sub.add_parser("logs"); p.add_argument("run_dir"); p.set_defaults(fn=cmd_logs)

    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
