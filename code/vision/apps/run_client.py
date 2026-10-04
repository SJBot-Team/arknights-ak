"""场景① 入口：识别并操控本地明日方舟客户端（纯 GUI，不读内存）。

特点：
- 只抓目标窗口客户区（比全屏快且不受遮挡影响）；
- 坐标支持相对归一化（换分辨率不用改流水线）；
- 默认 --dry-run（只识别、不操作），确认无误再去掉；
- 急停：pydirectinput 的 FAILSAFE（鼠标甩到屏幕角落即中断）+ Ctrl+C。

用法：
    python apps/run_client.py --window "明日方舟" --pipeline pipelines/demo.json --dry-run --seconds 30
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from kernel import Engine, Pipeline  # noqa: E402
from kernel.window import list_windows  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", default="明日方舟", help="窗口标题关键字")
    ap.add_argument("--process", type=int, default=None, help="可选：进程 PID")
    ap.add_argument("--pipeline", default=None, help="流水线 JSON 路径")
    ap.add_argument("--seconds", type=float, default=60.0, help="运行时长上限")
    ap.add_argument("--fps", type=int, default=60, help="目标帧率")
    ap.add_argument("--dry-run", action="store_true", help="只识别，不执行鼠标键盘动作")
    ap.add_argument("--list-windows", action="store_true", help="只列出可见窗口")
    ap.add_argument("--focus", action="store_true", help="运行前把窗口切到前台")
    ap.add_argument("--capture-region", default=None,
                    help="相对窗口的裁剪 [l,t,r,b]（0~1），如 0.5,0.5,1,1 只抓右下角")
    args = ap.parse_args()

    if args.list_windows:
        for w in list_windows():
            print(f"  hwnd={w['hwnd']:<10} pid={w['pid']:<8} {w['title'][:70]}")
        return

    cfg = {
        "target_fps": args.fps,
        "capture": ["bettercam", "dxcam", "mss"],
        "input": [] if args.dry_run else ["directinput", "sendinput"],
        "window": {"title": args.window, "process": args.process, "auto_focus": args.focus},
        "templates": "templates",
        "plugins": "plugins",
    }
    if args.capture_region:
        cfg["capture_region_rel"] = [float(x) for x in args.capture_region.split(",")]

    engine = Engine(cfg, root=ROOT, verbose=True)
    try:
        engine.open()
    except Exception as exc:
        print(f"[错误] 启动失败: {exc!r}")
        print("提示：先用 --list-windows 确认窗口标题；窗口需处于可见状态。")
        return 1

    print(f"[模式] {'DRY-RUN（只识别）' if args.dry_run else '实操作（会移动鼠标键盘！）'}")
    print("[急停] 把鼠标快速甩到屏幕任一角落即可中断（FAILSAFE）")
    try:
        stats = engine.run(pipeline=args.pipeline, seconds=args.seconds, stop_when_finished=False)
    except KeyboardInterrupt:
        print("\n[中断] 用户停止")
        stats = {"interrupted": True}
    finally:
        engine.close()

    print("\n=== 运行统计 ===")
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
