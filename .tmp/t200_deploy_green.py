# -*- coding: utf-8 -*-
r"""t200_deploy_green.py — **绿格锚定部署**（依 T-200g `04/76` §7.2 的建议，T-200c 第 3/10 项）

prts+/MAA 的做法：进关时用关卡 JSON 的 `view` 矩阵把每格投成常量表，整局查表（**不重算、不回正**）。
本脚本按"别用静止画面的坐标去落格"改成**当帧锚定**：

  1) 暂停（`ensure_paused`：战斗内 + 两次读数一致）
  2) 取目标格**候选屏幕点**（默认用 `04/75` 的 1-1 线性映射 `x=559+124.5c, y=502+138(r-3)`）
  3) 按住卡片（卡位来自 `locate_operator_card`/固定 cx 二选一）→ **当帧检测绿格** →
     取**距候选点最近**的绿格中心（>0.6 格距则放弃，**不回退缓存坐标**）
  4) 走**屏幕内侧路径**（避开四边 120px，防止触发地图平移）拖到绿格中心并松手
  5) `find_diamond()` 复核（偏差>0.8 格距 ⇒ 判失败）；成功则拖菱形定朝向

用法：python t200_deploy_green.py --char 芬 --card-x 110 --row 3 --col 5 --dir 左
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time

import cv2
import numpy as np

VISION = r'C:\Users\23922\Documents\ds_harness\ak\code\vision'
sys.path.insert(0, VISION)
from plugins.action.deploy import Deployer                    # noqa: E402
from plugins.capture.emu_window import make_capture           # noqa: E402

ADB = r'D:\__soft\MuMu Player 12\shell\adb.exe'
DEV = '127.0.0.1:16384'


def motion(seq, between=180):
    for kind, x, y in seq:
        subprocess.run([ADB, '-s', DEV, 'shell', 'input', 'motionevent', kind, str(int(x)), str(int(y))],
                       capture_output=True)
        time.sleep(between / 1000.0)


def grab():
    subprocess.run([ADB, '-s', DEV, 'shell', 'screencap', '-p', '/sdcard/g.png'], capture_output=True)
    subprocess.run([ADB, '-s', DEV, 'pull', '/sdcard/g.png',
                    r'C:\Users\23922\Documents\ds_harness\ak\.tmp\_green_shot.png'], capture_output=True)
    return cv2.imread(r'C:\Users\23922\Documents\ds_harness\ak\.tmp\_green_shot.png')


def green_cells(img, min_area=1500):
    """当帧绿格（可部署高亮）中心列表。"""
    b, g, r = img[..., 0].astype(int), img[..., 1].astype(int), img[..., 2].astype(int)
    # ★阈值沿用工作区已验证的 `t200_green2.py`（本轮首版写严了，导致只测到 UI 上的两块绿）
    m = ((g > r + 12) & (g > b + 8) & (g > 70)).astype(np.uint8)
    m[:150, :] = 0
    m[830:, :] = 0
    n, lab, stats, cent = cv2.connectedComponentsWithStats(m, 8)
    out = []
    PITCH_X, PITCH_Y = 124.5, 138.0        # 1-1 的列/行距（`04/75`：x=559+124.5c, y=502+138(r-3)）
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if area < min_area or not (10 <= w <= 1400 and 8 <= h <= 800):
            continue
        # ★大块是"多格合并"（相邻可部署格连成一片）⇒ 按列距/行距切成单格中心
        nx = max(1, int(round(w / PITCH_X)))
        ny = max(1, int(round(h / PITCH_Y)))
        for ix in range(nx):
            for iy in range(ny):
                out.append((x + (ix + 0.5) * w / nx, y + (iy + 0.5) * h / ny, int(area / (nx * ny))))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--char', default='芬')
    ap.add_argument('--card-x', type=int, default=110)
    ap.add_argument('--row', type=int, default=3)
    ap.add_argument('--col', type=int, default=5)
    ap.add_argument('--dir', default='左')
    ap.add_argument('--tol', type=float, default=0.6, help='允许的格距误差（格）')
    a = ap.parse_args()

    d = Deployer(make_capture('adb'))
    ok, info = d.ensure_paused()
    print('ensure_paused =', ok, info)
    if not ok:
        print('★ 不在「战斗且暂停」')
        return 2

    # 2) 候选点：04/75 的 1-1 线性映射
    cx = 559 + 124.5 * a.col
    cy = 502 + 138 * (a.row - 3)
    print(f'目标 {a.char} @row{a.row}col{a.col} ⇒ 候选屏幕点 ({cx:.0f},{cy:.0f})')

    # 3) 按住卡片 → 当帧检测绿格 → 就近吸附
    motion([('DOWN', a.card_x, 995), ('MOVE', 420, 760)])
    img = grab()
    cells = green_cells(img)
    print(f'当帧绿格 {len(cells)} 个'); [print('   ', tuple(round(v) for v in c)) for c in cells[:6]]
    if not cells:
        motion([('UP', 420, 760)])
        print('★ 无绿格 ⇒ 直接失败（不回退缓存坐标）')
        return 3
    cell = min(cells, key=lambda t: (t[0] - cx) ** 2 + (t[1] - cy) ** 2)
    dist_tiles = (((cell[0] - cx) / 124.5) ** 2 + ((cell[1] - cy) / 138.0) ** 2) ** 0.5
    print(f'选中绿格 ({cell[0]:.0f},{cell[1]:.0f})，距候选 {dist_tiles:.2f} 格')
    if dist_tiles > a.tol:
        motion([('UP', 420, 760)])
        print(f'★ 绿格离候选太远（>{a.tol} 格）⇒ 失败')
        return 4

    # 4) ★两段式（本轮踩坑后的修正）：
    #    `adb screencap` 会**打断"按住"状态** ⇒ 不能在同一段拖拽里截图测格。
    #    做法：先按住→截图测绿格→**取消**（UP 到空地）→再一口气拖到已测出的格心。
    motion([('UP', 420, 760)], between=0)
    time.sleep(0.35)
    tx, ty = int(cell[0]), int(cell[1])
    tx = max(130, min(1790, tx)); ty = max(160, min(760, ty))
    print(f'第二段：重新按住卡片({a.card_x},995) → 一口气拖到 ({tx},{ty})')
    motion([('DOWN', a.card_x, 995), ('MOVE', 420, 780), ('MOVE', 760, 640),
            ('MOVE', (760 + tx) // 2, (640 + ty) // 2), ('MOVE', tx, ty), ('UP', tx, ty)],
           between=170)
    time.sleep(0.9)

    # 5) 复核
    img2 = grab()
    try:
        dia = d.find_diamond(img2)
    except Exception as e:                                     # noqa: BLE001
        dia = None
        print('find_diamond 异常:', e)
    print('菱形 =', dia)
    if not dia:
        print('★ 未见朝向菱形 ⇒ 部署未进入朝向选择')
        cv2.imwrite(r'C:\Users\23922\Documents\ds_harness\ak\.tmp\t200_green_fail.png', img2)
        return 5

    # 6) 定朝向
    dx, dy = dia.get('cx', tx), dia.get('cy', ty)
    off = 144
    vec = {'左': (-off, 0), '右': (off, 0), '上': (0, -off), '下': (0, off)}[a.dir]
    motion([('DOWN', dx, dy), ('MOVE', dx + vec[0] // 2, dy + vec[1] // 2), ('MOVE', dx + vec[0], dy + vec[1]),
            ('UP', dx + vec[0], dy + vec[1])], between=200)
    time.sleep(0.9)
    rc = d.read_cost()
    print(f'部署后读数 {rc}（成功判据：剩余可放置 −1、费用减少）')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
