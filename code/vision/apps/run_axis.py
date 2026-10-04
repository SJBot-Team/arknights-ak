# -*- coding: utf-8 -*-
r"""run_axis.py — 轴表执行入口（打图端，默认 dry-run）

与模拟器共用同一份轴表 JSON；时间基准来自「逻辑帧时钟」（费用尺优先，见
plugins/clock/cost_ruler.py），操作注入走可插拔输入后端（默认 ADB，不占宿主鼠标）。

安全默认 / 合规（用户 2026-09-14 声明，见 ak/meta/合规声明_自动打图与账号.md）：
  * 默认 **dry-run**：不注入任何输入，只打印每条操作的「目标帧 / 实际帧 / 迟到帧」；
  * 实注入需显式 `--live` **且** 配置 `compliance.live_run_consent=true` **或**命令行 `--i-have-consent`
    （二者其一，代表用户当场同意）；否则拒绝执行；
  * **登录动作默认禁用**（`compliance.login_actions_enabled`）；本脚本不会执行任何登录/换号操作；
  * **禁止动用除「理智」外的账号资源**：本脚本只做关卡内操作（部署/技能/撤退），
    不得打开仓库/基建/抽卡/商店等界面，误触立即退出；
  * 练度/模组不匹配 → 停止并请示用户，**不得自行提升**；
  * 不读写游戏文件、不访问进程内存（仅截图 / 本机回环 API / ADB 注入）。

用法：
    cd ak/code/vision
    # 1) 干跑（无需游戏、无需尺子；用虚拟时钟把整条轴走一遍）
    & '.\.venv\Scripts\python.exe' -X utf8 apps\run_axis.py --config configs\axis_h12-4.json

    # 2) 接费用尺 + 干跑（需要尺子在跑，验证真实帧时钟）
    & '...python.exe' -X utf8 apps\run_axis.py --config configs\axis_h12-4.json --clock ruler

    # 3) 实注入（需用户当场同意；先在游戏内摆好编队并进入关卡）
    & '...python.exe' -X utf8 apps\run_axis.py --config configs\axis_h12-4.json --clock ruler --live --i-have-consent
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from kernel.registry import TASKS, load_plugins     # noqa: E402


class _Runner:
    """最小 engine 替身：只提供任务需要的 config / input / grab。"""

    def __init__(self, config: dict, backend=None, capture=None):
        self.config = config
        self.input = backend
        self._capture = capture
        self.ctx = None

    def grab(self):
        if self._capture is None:
            raise RuntimeError('当前配置需要截图（cost_bar 时钟/识别），但未启用采集后端')
        return self._capture()


def _make_capture(cfg: dict):
    """可选：用内核采集后端抓窗口（成本条识别兜底时钟需要）。"""
    try:
        from kernel.engine import Engine
        eng = Engine({'capture': cfg.get('capture', ['bettercam', 'dxcam', 'mss']),
                      'window': cfg.get('window', {}),
                      'plugins': os.path.join(ROOT, 'plugins')}, root=ROOT, verbose=False)
        eng.open()
        return eng
    except Exception as ex:
        print(f'[run_axis] 截图后端不可用: {ex!r}')
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', required=True, help='轴执行配置 JSON（含 axis_runner 段）')
    ap.add_argument('--clock', default=None, choices=['auto', 'ruler', 'cost_bar', 'virtual'],
                    help='覆盖配置里的时钟源')
    ap.add_argument('--timebase', default=None, choices=['cost-relative', 'abs-seconds'],
                    help='覆盖轴表时基（默认 cost-relative）')
    ap.add_argument('--live', action='store_true', help='真的注入操作（默认 dry-run，且需合规同意）')
    ap.add_argument('--i-have-consent', action='store_true',
                    help='声明「用户已当场同意本次实注入」（合规声明要求；等价于配置 compliance.live_run_consent=true）')
    ap.add_argument('--speed', type=float, default=None, help='虚拟时钟加速倍率（dry-run 用）')
    args = ap.parse_args()

    with open(args.config, encoding='utf-8') as f:
        raw = json.load(f)
    comp = dict(raw.get('compliance') or {})
    cfg = raw.get('axis_runner', raw)

    # ---------- 合规守卫（用户 2026-09-14 声明） ----------
    if args.live:
        consented = bool(args.i_have_consent or comp.get('live_run_consent'))
        if not consented:
            print('[合规] 拒绝实注入：需用户当场同意。\n'
                  '       做法：把配置 compliance.live_run_consent 置 true，或加 --i-have-consent。\n'
                  '       声明见 ak/meta/合规声明_自动打图与账号.md')
            return 2
        if comp.get('login_actions_enabled'):
            print('[合规] 警告：配置里 login_actions_enabled=true。本脚本不执行任何登录动作，'
                  '登录必须逐次获用户同意（见合规声明 §一）。')
        print(f'[合规] 允许账号={comp.get("allowed_accounts")} '
              f'登录额度={comp.get("login_quota")} 已用={comp.get("login_quota_used")} '
              f'仅允许消耗={comp.get("consume_only")}')
        print(f'[合规] 禁止界面={"、".join(comp.get("forbidden_ui") or [])}；'
              f'禁止操作={"、".join(comp.get("forbidden_actions") or [])}')

    if args.clock:
        cfg.setdefault('clock', {})['source'] = args.clock
    if args.timebase:
        cfg['timebase'] = args.timebase
    cfg['dry_run'] = not args.live
    if args.speed:
        cfg['virtual_speed'] = args.speed

    load_plugins(os.path.join(ROOT, 'plugins'))
    runner_cls = TASKS['axis_runner']

    backend = None
    capture = None
    engine = _Runner({'axis_runner': cfg})
    if not cfg['dry_run']:
        icfg = dict(cfg.get('input') or {})
        name = icfg.pop('backend', 'input:adb')
        from kernel.registry import ACTIONS
        backend = ACTIONS[name](**icfg)
        print(f'[run_axis] 输入后端 {name}：{backend!r}')
    if str((cfg.get('clock') or {}).get('source', 'auto')) in ('cost_bar',):
        engine_ = _make_capture(cfg)
        if engine_ is not None:
            engine._capture = lambda: engine_.grab()
    engine.input = backend

    print(f'[run_axis] 模式={"实注入" if args.live else "dry-run"} '
          f'时钟={(cfg.get("clock") or {}).get("source", "auto")} '
          f'时基={cfg.get("timebase", "cost-relative")}')
    res = runner_cls().run(engine)
    print(json.dumps({k: v for k, v in res.items() if k != 'log'}, ensure_ascii=False, indent=1))
    late = [r for r in res.get('log', []) if r.get('late_real_frames', 0) > 0.5]
    if late:
        print(f'[run_axis] 迟到 >0.5 帧的操作 {len(late)} 条：')
        for r in late[:10]:
            print(f'   #{r["idx"]+1} 目标 {r["target_frame"]} 实际 {r["frame_before"]} '
                  f'{r["op"]} {r["unit"]}')
    return 0 if res.get('ok') else 1


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
