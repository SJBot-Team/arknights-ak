# -*- coding: utf-8 -*-
"""deploy.py — **战斗内操作协议：部署 / 撤退 / 技能**（可复用封装）

## 依据
`knowledge/04/49_战斗内操作协议_部署.md`（2026-09-15 实测打通）：
- **部署 = 两段 motionevent 拖拽序列**（暂停态执行，对应 MAA `BattleDeployWhenPause`）：
  ① `DOWN(卡片) → MOVE(中间点…) → UP(格子)` ⇒ 进入朝向选择（出现白色菱形 + 「点击取消」）
  ② `DOWN(菱形中心) → MOVE → UP(方向角)` ⇒ 部署完成
- **关键**：`input tap` / `input swipe` **都不行**，必须用 **`motionevent` 带中间点的序列**。
- 成功判据：卡片消失 + 「剩余可放置角色」−1 + 干员出现在战场。

## 坐标基准
全部为**帧坐标**（1920×1080）。卡片中心 x 由 `card_centers()` 给出（实测 12 张）。

## 用法
    from plugins.action.deploy import Deployer
    d = Deployer(cap, adb_path, '127.0.0.1:16384')
    d.pause()                       # 确认暂停（MAA: 暂停态部署）
    ev = d.deploy_timed(card_xy=(88, 995), grid_xy=(1200, 400), direction='down')
    print(ev)                       # {'cost_before':..,'tick_before':..,'cost_after':..,'tick_after':..}
"""
from __future__ import annotations

import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

ADB = r'D:\__soft\MuMu Player 12\shell\adb.exe'
DEV = '127.0.0.1:16384'
# 朝向菱形四角相对中心的偏移（实测：中心(1063,252) → 下角(1063,396) ⇒ ±144）
DIR_OFFSET = {'down': (0, 144), 'up': (0, -144), 'left': (-144, 0), 'right': (144, 0)}
CARD_Y = 995
CARD_X = [87, 242, 387, 551, 719, 891, 1036, 1262, 1369, 1527, 1689, 1855]
PAUSE_BTN = (1877, 76)


class Deployer:
    def __init__(self, cap, adb: str = ADB, dev: str = DEV, card_x=None, card_y: int = CARD_Y):
        self.cap = cap
        self.adb = adb
        self.dev = dev
        self.card_x = card_x or CARD_X
        self.card_y = card_y
        self.log = []

    # ---------- 底层输入 ----------
    def _sh(self, *args):
        return subprocess.run([self.adb, '-s', self.dev, 'shell', *map(str, args)],
                              capture_output=True)

    def tap(self, x, y):
        self._sh('input', 'tap', int(x), int(y))

    def motion(self, points, hold_ms=120, between_ms=120):
        """带中间点的拖拽序列 —— 这是游戏唯一认的拖拽方式。

        points: [(x,y), ...] 至少两点（起点、终点）。
        """
        (x0, y0) = points[0]
        self._sh('input', 'motionevent', 'DOWN', int(x0), int(y0))
        for (x, y) in points[1:]:
            time.sleep(between_ms / 1000.0)
            self._sh('input', 'motionevent', 'MOVE', int(x), int(y))
        time.sleep(hold_ms / 1000.0)
        (xe, ye) = points[-1]
        self._sh('input', 'motionevent', 'UP', int(xe), int(ye))

    def key(self, code=4):
        self._sh('input', 'keyevent', str(code))

    # ---------- 暂停 / 恢复 ----------
    def is_paused(self, wait: float = 1.0):
        """判定是否暂停：**读两次费用与相位，两者都不变才算暂停**（上轮踩坑：单次点击后未确认）。"""
        a = self.read_cost()
        time.sleep(wait)
        b = self.read_cost()
        return (a['fill_px'] == b['fill_px'] and a['cost'] == b['cost'] and a['tick'] == b['tick']), a, b

    def ensure_paused(self, tries: int = 3):
        """★强制前置：确保游戏处于**战斗中且已暂停**（MAA `BattleDeployWhenPause` 要求）。

        注意（上轮踩坑）：非战斗界面（如关卡地图 viewport）画面本身静止，
        会被"两次读数相同"误判为暂停 ⇒ **必须先确认界面是 battle**。
        返回 (ok, 读数/原因)。
        """
        from plugins.recognize.ui_state import UiState
        ui = UiState()
        for i in range(tries):
            img = self.cap.grab().image
            st = ui.classify(img)['state']
            if st != 'battle':
                return False, {'state': st, 'reason': 'not_in_battle'}
            ok, a, b = self.is_paused()
            if ok:
                return True, a
            self.tap(*PAUSE_BTN)
            time.sleep(1.6)
        img = self.cap.grab().image
        st = ui.classify(img)['state']
        if st != 'battle':
            return False, {'state': st, 'reason': 'not_in_battle'}
        ok, a, _ = self.is_paused()
        return ok, a

    def pause(self):
        self.tap(*PAUSE_BTN)
        time.sleep(1.5)

    def resume(self):
        self.tap(*PAUSE_BTN)
        time.sleep(0.3)

    # ---------- 实机时刻 → 游戏内帧（与模拟器同一时间轴） ----------
    @staticmethod
    def frame_of(cost, tick, initial_cost: int = 10):
        """★把实机的 (当前费用, 费用条相位) 换算成**游戏内帧**。

        依据（均已独立验证）：费用条满一次 = 30 帧；相位由官方 pixel_map 查表（中位 0~1 帧）。
            frame = (cost - initial_cost) * 30 + tick
        **仅在"费用未封顶"时成立**：封顶期间条静止、相位失效，需先用上限锚点续接。
        """
        if cost is None or tick is None:
            return None
        return int(round((cost - initial_cost) * 30 + tick))

    # ---------- 读数（费用 + 相位） ----------
    def read_cost(self, img=None):
        from plugins.recognize.cost_number import CostNumberRecognizer
        from plugins.clock.frame_clock import PIXEL_MAP_30F, bar_phase, frame_from_width
        img = self.cap.grab().image if img is None else img
        if not hasattr(self, '_rec'):
            self._rec = CostNumberRecognizer()
            self._spec = {'roi': [1795, 730, 1915, 805],
                          'templates': r'C:\Users\23922\Documents\ds_harness\ak\.tmp\tpl_h124.json'}
        ms = self._rec.run(img, self._spec, None, (0, 0))
        cost = None
        if ms and float(ms[0].extra.get('confidence', 0.0)) >= 0.85:
            cost = int(ms[0].extra['cost'])
        ph = bar_phase(img[805:818, 1739:1919], full_px=180)
        return {'cost': cost, 'fill_px': ph['fill_px'],
                'tick': frame_from_width(ph['fill_px'], PIXEL_MAP_30F)}

    # ---------- 待部署卡片检测（位置随卡片数量变化，必须动态检测） ----------
    def find_cards(self, img=None, y_band=(940, 1075), min_w: int = 60):
        """★待部署卡片检测（改进版：列梯度 + 列亮度 双通道分段）。

        为什么必须检测：卡片位置随数量与排序变化（实测 12 张时中心 x≈100…1858），
        硬编码坐标会点到**卡片之间的间隙**（表现为"点了没反应"或弹出敌人信息）。
        旧版仅用"列标准差"会**把相邻卡片合并成 1~2 段**（实测只返回 2 个），故改为：
          ① 列梯度能量（`Sobel_x` 列求和）找卡片边界；
          ② 列亮度均值找"亮块"（卡片是亮矩形、间隙是暗色）；
        取**分段数较多**的一路，再按宽度过滤。
        """
        import cv2
        import numpy as np
        img = self.cap.grab().image if img is None else img
        y0, y1 = y_band
        strip = img[y0:y1]
        gray = cv2.cvtColor(strip, cv2.COLOR_BGR2GRAY).astype(np.float32)

        col_energy = np.abs(cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)).sum(axis=0)
        col_bright = gray.mean(axis=0)

        def segments(sig, ratio=0.6):
            thr = sig.mean() * ratio
            mask = sig > thr
            segs, s = [], None
            for i, m in enumerate(mask):
                if m and s is None:
                    s = i
                elif not m and s is not None:
                    if i - s >= min_w:
                        segs.append((s, i))
                    s = None
            if s is not None and len(mask) - s >= min_w:
                segs.append((s, len(mask)))
            merged = []
            for a, b in segs:
                if merged and a - merged[-1][1] < 6:
                    merged[-1] = (merged[-1][0], b)
                else:
                    merged.append((a, b))
            return merged

        se, sb = segments(col_energy), segments(col_bright)
        best = sb if len(sb) >= len(se) else se
        yc = (y0 + y1) // 2
        return [{'cx': (a + b) // 2, 'cy': yc, 'x0': a, 'x1': b, 'w': b - a}
                for a, b in best if b - a >= min_w]

    # ---------- 绿色可部署高亮格检测（选中干员后出现） ----------
    def find_green_cells(self, img=None, min_area: int = 4000, split: bool = True,
                         cell_px: int = 130):
        """检测**选中干员后**游戏高亮出的"绿色可部署格"，返回中心列表（面积降序）。

        这是"格子定位"的自动化手段：不必人肉找可部署坐标，
        只要点一次卡片、检测绿格、取第一个作为落点即可。

        ★`split=True`（默认）：绿色高亮常是**多个相邻格子的联合区域**，
        直接取"连通域质心"可能落在**格子边界/不可部署处** ⇒ 改为按
        `cell_px`（实测约 130 帧像素）**网格切分**，返回**每个格子单元的中心**。

        1-3 的绿格实测为若干 130px 上下的方形块，故默认切分。
        """
        import cv2
        import numpy as np
        img = self.cap.grab().image if img is None else img
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, np.array((33, 55, 55)), np.array((95, 255, 255)))
        k5 = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        k17 = cv2.getStructuringElement(cv2.MORPH_RECT, (17, 17))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k5)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k17)
        cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cells = []
        for c in cnts:
            a = cv2.contourArea(c)
            if a < min_area:
                continue
            x, y, w, h = cv2.boundingRect(c)
            if not split:
                cells.append({'cx': x + w // 2, 'cy': y + h // 2, 'w': w, 'h': h,
                              'area': float(a)})
                continue
            # ★网格切分：按 cell_px 划成若干单元，取每单元中心（并在 mask 内校验）
            nx, ny = max(1, round(w / cell_px)), max(1, round(h / cell_px))
            cw, chh = w / nx, h / ny
            for iy in range(ny):
                for ix in range(nx):
                    cx = int(x + (ix + 0.5) * cw)
                    cy = int(y + (iy + 0.5) * chh)
                    # 该点附近须确有绿色（避免落在空洞/边界）
                    yy0, yy1 = max(0, cy - 12), min(mask.shape[0], cy + 12)
                    xx0, xx1 = max(0, cx - 12), min(mask.shape[1], cx + 12)
                    if mask[yy0:yy1, xx0:xx1].mean() < 120:
                        continue
                    cells.append({'cx': cx, 'cy': cy, 'w': int(cw), 'h': int(chh),
                                  'area': float(cw * chh)})
        cells.sort(key=lambda z: -z['area'])
        return cells

    # ---------- 朝向菱形检测（部署进度的关键：菱形中心=游戏吸附后的干员位置） ----------
    def find_diamond(self, img=None, min_area: int = 60000):
        """检测「朝向选择」的白色粗边框菱形，返回 (cx, cy, w, h)。

        实测：拖卡到格子后游戏会把干员**吸附到格心**，菱形以该点为中心，
        四角对应四个朝向（实测中心 (1063,333)、下角 (1063,522) ⇒ 半高约 190px）。
        注意：**不能拿"拖拽落点"当菱形中心**，否则定朝向会失败（已踩坑）。
        """
        import cv2
        img = self.cap.grab().image if img is None else img
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, th = cv2.threshold(gray, 215, 255, cv2.THRESH_BINARY)
        th = cv2.morphologyEx(th, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9)))
        cnts, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        best = None
        h_img, w_img = gray.shape[:2]
        for c in cnts:
            a = cv2.contourArea(c)
            if a < min_area:
                continue
            x, y, w, h = cv2.boundingRect(c)
            if abs(w - h) > 0.35 * max(w, h):
                continue
            if w > w_img * 0.9 or h > h_img * 0.9:
                continue
            if best is None or a > best[0]:
                best = (a, x + w // 2, y + h // 2, w, h)
        if best is None:
            return None
        return {'cx': best[1], 'cy': best[2], 'w': best[3], 'h': best[4], 'area': best[0]}

    def set_direction(self, diamond=None, direction='down'):
        """按检测到的菱形拖到目标方向的角。返回是否执行。"""
        d = diamond or self.find_diamond()
        if not d:
            return False
        cx, cy = d['cx'], d['cy']
        r = int(d['h'] * 0.45)
        ox, oy = {'down': (0, r), 'up': (0, -r), 'left': (-r, 0), 'right': (r, 0)}.get(direction, (0, r))
        self.motion([(cx, cy), (cx + ox // 2, cy + oy // 2), (cx + ox, cy + oy)], hold_ms=150)
        time.sleep(1.2)
        return True

    # ---------- 部署 ----------
    def deploy_two_step_px(self, card_xy, cell_xy, dir_xy, *, use_real_mouse=True,
                           steps: int = 8, hold: float = 0.07, between: float = 0.02,
                           settle: float = 0.9):
        """★**两段式部署（像素坐标版，已实机验证成功）** —— 有朝向的干员必须这样做。

        ## 依据（用户 2026-09-15 指点）
        > 「干员部署有两类：一类**先拖拽，松手后再拖拽朝向，松手部署**；
        >   一类单位**没有朝向**，拖拽后松开自动部署。」

        ⇒ 「拖拽 → 松手」**不是失败**：它进入**朝向选择阶段**（画面仍显示干员与「点击取消」，
        费用与"剩余可放置角色"此时**尚未变化**）；**再从目标格拖向朝向、松手**才真正提交。
        （本项目此前长把第一阶段误判为"落格提交未成功"，即 **D1**。）

        ## 参数（均为 **1920×1080 帧坐标**）
        - `card_xy`：待部署卡片中心（如芬 (63,949)）
        - `cell_xy`：目标格中心（如 D6 = (934,502)，由格点标定 `x=1556−124.5·col`、`y=502+138·(row−3)` 得到）
        - `dir_xy` ：**朝向点**：从 `cell_xy` 指向该方向的另一点（如朝 (3,4) 即 (1182,502)）

        `use_real_mouse=True` 走**真实鼠标**（`SetCursorPos`+`mouse_event`，实测提交成功）；
        否则走 ADB `motionevent`（`self.motion`）。返回 `{'ok', 'stage1', 'stage2'}`。
        """
        def _drag(pts):
            if use_real_mouse:
                return self._real_drag(pts, steps=steps, hold=hold, between=between)
            self.motion(pts, hold_ms=int(hold * 1000), between_ms=int(between * 1000))
            return True

        cx, cy = card_xy
        gx, gy = cell_xy
        mid = [((cx + gx) // 2, (cy + gy) // 2)]
        stage1 = _drag([(cx, cy)] + mid + [(gx, gy)])      # ① 拖到格 → 进入朝向选择
        time.sleep(settle)
        stage2 = _drag([(gx, gy), (dir_xy[0], dir_xy[1])])  # ② 拖朝向 → 提交
        time.sleep(settle)
        rec = {'ok': bool(stage1 and stage2), 'card': card_xy, 'cell': cell_xy,
               'dir': dir_xy, 'real_mouse': bool(use_real_mouse)}
        self.log.append(('deploy_two_step', rec))
        return rec

    def _real_drag(self, pts_frame, steps=8, hold=0.07, between=0.02):
        """真实鼠标拖拽（`SetCursorPos` + `mouse_event`）—— 宏层会把它翻译成触摸拖拽。"""
        import ctypes
        u32 = ctypes.windll.user32
        LD, LU = 0x0002, 0x0004
        from plugins.action.win_input import WinInput
        wi = WinInput()
        pts = [wi.to_screen(x, y) for (x, y) in pts_frame]
        u32.SetCursorPos(int(pts[0][0]), int(pts[0][1]))
        time.sleep(hold)
        u32.mouse_event(LD, 0, 0, 0, 0)
        time.sleep(hold)
        for (x0, y0), (x1, y1) in zip(pts[:-1], pts[1:]):
            for k in range(1, steps + 1):
                t = k / (steps + 1.0)
                u32.SetCursorPos(int(x0 + (x1 - x0) * t), int(y0 + (y1 - y0) * t))
                time.sleep(between)
        u32.SetCursorPos(int(pts[-1][0]), int(pts[-1][1]))
        time.sleep(hold)
        u32.mouse_event(LU, 0, 0, 0, 0)
        return True

    def deploy(self, card_xy, grid_xy, direction='down', mid_points=None, verify_wait=1.2,
               preselect: bool = True):
        """执行一次完整部署。返回 {'ok': bool, 'diamond': {...}}

        ★ `preselect`：**先点一次卡片进入「选择态」** —— 实测这是**必要条件**：
        不点则后续拖拽序列不被游戏识别（菱形检测为 None）。点击会顺带弹出干员详情面板，
        但选择态同时建立，且拖拽路径在屏幕下半部，不受详情面板遮挡影响。
        """
        cx, cy = card_xy
        gx, gy = grid_xy
        if preselect:
            self.tap(cx, cy)
            time.sleep(1.2)
        mids = mid_points or [(int((cx + gx) / 2), int(cy * 0.55 + gy * 0.45)),
                              (gx - 80, int(gy * 0.7 + cy * 0.3))]
        # ① 拖卡片到格子 ⇒ 进入朝向选择
        self.motion([(cx, cy)] + mids + [(gx, gy)])
        time.sleep(verify_wait)
        diamond = self.find_diamond()
        # ② 按检测到的菱形定朝向 ⇒ 完成部署
        done = self.set_direction(diamond, direction)
        return {'ok': bool(done), 'card': (cx, cy), 'grid': (gx, gy),
                'direction': direction, 'diamond': diamond}

    def deploy_timed(self, card_xy, grid_xy, direction='down', **kw):
        """部署 + 前后读数 ⇒ 产出「实机部署事件」记录（用于与模拟器事件时间线对照）。"""
        before = self.read_cost()
        t0 = time.time()
        r = self.deploy(card_xy, grid_xy, direction, **kw)
        dt = time.time() - t0
        after = self.read_cost()
        ev = {'wall_start': t0, 'wall_seconds': round(dt, 3),
              'cost_before': before['cost'], 'tick_before': before['tick'],
              'cost_after': after['cost'], 'tick_after': after['tick'],
              'cost_delta': (None if (before['cost'] is None or after['cost'] is None)
                             else after['cost'] - before['cost']),
              **r}
        self.log.append(ev)
        return ev

    # ---------- 撤退 / 技能（协议待实测，先提供入口） ----------
    def retreat(self, unit_xy, confirm_xy=None):
        """撤退：点单位 → 点确认（具体坐标需按实机标定）。"""
        self.tap(*unit_xy)
        time.sleep(0.8)
        if confirm_xy:
            self.tap(*confirm_xy)
        time.sleep(0.8)

    def skill(self, unit_xy):
        """开技能：点单位 → 点技能按钮（坐标需按实机标定）。"""
        self.tap(*unit_xy)
        time.sleep(0.8)


def card_centers(n=12):
    return [(CARD_X[i], CARD_Y) for i in range(min(n, len(CARD_X)))]


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    from plugins.capture.emu_window import make_capture
    d = Deployer(make_capture('adb'))
    print('当前读数:', d.read_cost())
    print('卡片中心:', card_centers())
