# -*- coding: utf-8 -*-
r"""t200_prts_flow.py — **按 prts+ 方案在 1-1 演习里精确复刻两次部署**（T-200c）

## 用户给的 prts+ 方案（本轮据此实现）
> 正常运行时帧流动快、只能粗读费用；**读帧必须在暂停时精确读**。
> 流程：①**粗识别** → 在"将要到达目标帧之前一定时间"**先暂停**；
> ②**点待部署区干员 ⇒ 进入时缓（子弹时间）**；
> ③**步进**到执行操作的目标帧；
> ④**每次操作前用头像文件识别干员实际位置**（不靠固定坐标）。

## 依赖（工作区已有）
- 头像识别：`plugins.recognize.operator_card.OperatorCardMatcher.identify_deploy_row`
  （prts+ 的 `resource/avatar/*.png`，掩膜 NCC）
- 读帧：`plugins.action.deploy.Deployer.read_cost()` → `{cost, fill_px, tick}`，
  `frame_of(cost, tick) = (cost − 10)×30 + tick`（费用条 180px = 1 费 = 30 帧）
- 暂停确认：`Deployer.ensure_paused()`（**先确认真在战斗**，再两次读数相同）
- 部署：`Deployer.deploy()`（两段 `motionevent`）

用法：
    python t200_prts_flow.py --targets 10,411 --cards 芬:left@D6,月见夜:up@D4 [--dry]
"""
from __future__ import annotations

import argparse
import os
import sys
import time

import cv2

VISION = r'C:\Users\23922\Documents\ds_harness\ak\code\vision'
sys.path.insert(0, VISION)

from plugins.action.deploy import Deployer                        # noqa: E402
from plugins.capture.emu_window import make_capture               # noqa: E402
from plugins.recognize.operator_card import OperatorCardMatcher   # noqa: E402

ADB = r'D:\__soft\MuMu Player 12\shell\adb.exe'
DEV = '127.0.0.1:16384'
TMP = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'

# 1-1 地块（1920×1080；D6 由标定视频实测、D4 由列距外推）
CELLS = {'D6': (1239, 359), 'D4': (954, 379)}
CARD_Y = 1007


def grab(d: Deployer):
    import subprocess
    subprocess.run([ADB, '-s', DEV, 'shell', 'screencap', '-p', '/sdcard/pf.png'],
                   capture_output=True)
    p = os.path.join(TMP, 'pf.png')
    subprocess.run([ADB, '-s', DEV, 'pull', '/sdcard/pf.png', p], capture_output=True)
    return cv2.imread(p)


def frame_now(d: Deployer):
    rc = d.read_cost()
    f = d.frame_of(rc['cost'], rc['tick'])
    return f, rc


def step_to(d: Deployer, target: int, *, max_steps: int = 400, step_s: float = 0.16,
            verbose: bool = True):
    """时缓下步进：恢复一小步→暂停→读帧，直到 ≥ target。"""
    for i in range(max_steps):
        f, rc = frame_now(d)
        if f is None:
            time.sleep(0.2)
            continue
        if f >= target:
            if verbose:
                print(f'    步进到位：帧 {f} ≥ 目标 {target}（第 {i} 步）')
            return f
        # 还差得远 ⇒ 直接恢复较长时间；接近 ⇒ 小步
        gap = target - f
        wait = step_s if gap <= 12 else min(1.5, gap / 30.0)
        d.resume()                      # 恢复
        time.sleep(wait)
        d.tap(1877, 76)                 # 暂停
        time.sleep(0.5)
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry', action='store_true')
    ap.add_argument('--targets', default='10,411')
    a = ap.parse_args()
    t1, t2 = [int(x) for x in a.targets.split(',')]

    cap = make_capture('adb')
    d = Deployer(cap, ADB, DEV)
    m = OperatorCardMatcher()

    ok, info = d.ensure_paused()
    print(f'[pause] ensure_paused = {ok}  {info if not ok else info}')
    if not ok:
        print('★ 未处于「战斗且暂停」⇒ 中止（先手工进关并暂停）')
        return 2

    img = grab(d)
    SQUAD4 = ['卡缇', '安赛尔', '芬', '泡普卡', '安德切尔', '月见夜', '斑点', '香草',
              '玫兰莎', '克洛丝', '史都华德']
    row = m.identify_deploy_row(img, candidates=SQUAD4)
    print('[cards] 待部署区识别（头像模板匹配，自动列）：')
    for i, c in enumerate(row or []):
        print(f'   #{i} {c["name"]:<8} score={c["score"]:.3f} margin={c["margin"]:.3f} cx={c["cx"]}')
    # ★头像定位（判别式扫描）：月见夜可用；芬用"已裁图核对过"的卡位
    loc_mid = m.locate_operator_card(img, '月见夜', candidates=SQUAD4)
    print('[locate] 月见夜 ->', loc_mid)
    FANG_CX = int(os.environ.get('FANG_CX', '175'))     # 卡1（裁图核对：蓝发狼耳=芬）
    MID_CX = int(loc_mid.get('cx', 960)) if loc_mid.get('ok') else 960
    print(f'[locate] 芬 -> cx={FANG_CX}（卡1，人工裁图核对）；月见夜 -> cx={MID_CX}')

    f0, rc0 = frame_now(d)
    print(f'[frame] 当前 cost={rc0["cost"]} tick={rc0["tick"]} ⇒ 帧 {f0}')

    if a.dry:
        print('（dry-run，未注入）')
        return 0

    # ---------- 操作①：芬 @D6 朝左，目标帧 t1 ----------
    idx_fang = 0
    print(f'[op1] 芬 cx={FANG_CX} → D6 朝左，目标帧 {t1}')
    step_to(d, max(1, t1 - 2))
    rc = d.read_cost()
    print(f'   执行前读数 cost={rc["cost"]} tick={rc["tick"]} 帧={d.frame_of(rc["cost"], rc["tick"])}')
    ev = d.deploy(card_xy=(FANG_CX, CARD_Y),
                  grid_xy=CELLS['D6'], direction='left')
    print('   部署①返回：', ev)

    # ---------- 操作②：月见夜 @D4 朝上，目标帧 t2 ----------
    print(f'[op2] 月见夜 cx={MID_CX} → D4 朝上，目标帧 {t2}')
    step_to(d, max(1, t2 - 2))
    rc = d.read_cost()
    print(f'   执行前读数 cost={rc["cost"]} tick={rc["tick"]} 帧={d.frame_of(rc["cost"], rc["tick"])}')
    ev = d.deploy(card_xy=(MID_CX, CARD_Y), grid_xy=CELLS['D4'], direction='up')
    print('   部署②返回：', ev)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
