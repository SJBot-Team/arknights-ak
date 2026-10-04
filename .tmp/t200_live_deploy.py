# -*- coding: utf-8 -*-
r"""t200_live_deploy.py — 1-1 演习：**暂停态 + motionevent 拖拽**复刻标定的两次部署（T-200c）

依 `knowledge/04/49_战斗内操作协议_部署.md`：
  · 部署**必须用 `input motionevent` 的 DOWN→MOVE→UP 序列**（`tap`/`swipe` 都不行）；
  · 部署**在暂停态执行**（MAA `BattleDeployWhenPause`）；
  · 朝向：部署后出现白色菱形，第二段 motionevent 从菱形中心拖到方向角（±144px）；
  · 成功判据：卡片消失 + 「剩余可放置角色」−1 + 干员出现在战场。

本脚本：进入战斗 → 暂停 → 部署①(D6 朝左) → 恢复 12.5s → 暂停 → 部署②(D4 朝上) → 逐帧报告。
用法：python t200_live_deploy.py [--dry]
"""
from __future__ import annotations

import subprocess
import sys
import time

from PIL import Image

ADB = r'D:\__soft\MuMu Player 12\shell\adb.exe'
DEV = '127.0.0.1:16384'
TMP = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'

CARD_Y = 995
CARD_X = [87, 242, 387, 551, 719, 891, 1036, 1262, 1369, 1527, 1689, 1855]
PAUSE_BTN = (1877, 76)
DIR = {'down': (0, 144), 'up': (0, -144), 'left': (-144, 0), 'right': (144, 0)}

# 标定表目标：帧10 芬@D6 朝左；帧411 月见夜@D4 朝上（1920×1080 触发坐标）
D6 = (1239, 359)
D4 = (954, 379)


def sh(*a):
    return subprocess.run([ADB, '-s', DEV, 'shell', *map(str, a)], capture_output=True)


def tap(x, y):
    sh('input', 'tap', int(x), int(y))


def motion(pts, hold=140, between=140):
    """游戏唯一认的拖拽：DOWN → MOVE… → UP。"""
    sh('input', 'motionevent', 'DOWN', int(pts[0][0]), int(pts[0][1]))
    for (x, y) in pts[1:]:
        time.sleep(between / 1000.0)
        sh('input', 'motionevent', 'MOVE', int(x), int(y))
    time.sleep(hold / 1000.0)
    sh('input', 'motionevent', 'UP', int(pts[-1][0]), int(pts[-1][1]))


def shot(path):
    sh('screencap', '-p', '/sdcard/x.png')
    subprocess.run([ADB, '-s', DEV, 'pull', '/sdcard/x.png', path], capture_output=True)
    return path


def paused(path) -> bool:
    """暂停判据：中央的白色 'PAUSE' 大字区域足够亮。"""
    im = Image.open(path).convert('L').crop((700, 380, 1150, 470))
    px = list(im.getdata())
    bright = sum(1 for v in px if v > 170) / max(1, len(px))
    return bright > 0.05


def main() -> int:
    dry = '--dry' in sys.argv
    from_squad = '--from-squad' in sys.argv
    print('=== 1-1 演习：暂停态 motionevent 部署复刻 ===')

    # ---- 1) 进关 ----
    if from_squad:
        tap(1740, 780)         # 开始行动（已在编队页）
        time.sleep(6.5)
    elif not dry:
        tap(960, 950)          # 结算继续
        time.sleep(4)
        tap(904, 510)          # 1-1 节点
        time.sleep(4)
        tap(1480, 1000)        # 演习
        time.sleep(5)
        tap(1740, 780)         # 开始行动
        time.sleep(6.5)

    # ---- 2) 暂停并确认 ----
    for attempt in range(4):
        tap(*PAUSE_BTN)
        time.sleep(0.9)
        p = shot(f'{TMP}\\live_pause{attempt}.png')
        if paused(p):
            print(f'  [pause] 第 {attempt+1} 次点击后确认暂停 ✓')
            break
    else:
        print('  [pause] ★ 未确认暂停，继续尝试')
    cost_shot = shot(f'{TMP}\\live_before1.png')
    print(f'  部署前截图：{cost_shot}')

    if dry:
        print('（dry-run，未注入）')
        return 0

    # ---- 3) 部署①：芬(卡3) → D6 朝左 ----
    print('  [deploy1] 卡3(芬) → D6(1239,359)，定向=左')
    motion([(CARD_X[2], CARD_Y), (600, 700), D6])
    time.sleep(0.8)
    motion([D6, (D6[0] + DIR['left'][0], D6[1] + DIR['left'][1])])
    time.sleep(1.2)
    print('  部署①后截图：', shot(f'{TMP}\\live_after1.png'))

    # ---- 4) 恢复到目标帧附近（帧411 ≈ 13.7s；已用约 1s）----
    print('  [step] 恢复 12.4s 后暂停（目标 ≈ 帧 411）')
    tap(*PAUSE_BTN)            # 恢复
    time.sleep(12.4)
    for attempt in range(4):
        tap(*PAUSE_BTN)
        time.sleep(0.8)
        p = shot(f'{TMP}\\live_pause_b{attempt}.png')
        if paused(p):
            print(f'  [pause] 二次暂停确认 ✓（第 {attempt+1} 次点击）')
            break
    print('  二次暂停后截图：', shot(f'{TMP}\\live_before2.png'))

    # ---- 5) 部署②：月见夜(卡6) → D4 朝上 ----
    print('  [deploy2] 卡6(月见夜) → D4(954,379)，定向=上')
    motion([(CARD_X[5], CARD_Y), (600, 600), D4])
    time.sleep(0.8)
    motion([D4, (D4[0], D4[1] + DIR['up'][1])])
    time.sleep(1.2)
    print('  部署②后截图：', shot(f'{TMP}\\live_after2.png'))

    print('=== 完成：请核对 live_after1/2.png 的「剩余可放置角色」是否 8→7→6 ===')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
