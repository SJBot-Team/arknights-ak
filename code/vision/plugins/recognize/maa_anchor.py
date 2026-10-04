# -*- coding: utf-8 -*-
"""maa_anchor.py — 基于 **MAA 现成资源**的界面锚点识别（用户 2026-09-14 建议）

## 为什么用它
我此前手写判据（"能读到数字=在战斗"、"右下角白色占比=squad"）与猜测坐标反复出错：
点击落空、把结算画面误判成战斗、章节跑偏。MAA 有成套**验证过的**界面模板、ROI 与点击语义，
直接借用比自造可靠得多。

## 关键事实（来自 D:\\__soft\\MAA\\resource）
- MAA 的 ROI 基准分辨率是 **1280×720**；本项目实机帧是 **1920×1080**（同为 16:9）⇒ **×1.5** 换算。
- `template/Battle/StartButton/BattleStartNormal.png`、`BattleStartExercise.png`（**演习**）… =
  界面右下方那个大按钮的模板。
- `tasks/tasks.json`：
  · `BattleStartPre`（OCR「开始行动/作战/突袭/试炼…」）ROI `[1000,600,280,120]` → 中心 (1140,660)@1280
    ⇒ **@1920 = (1710, 990)**（我之前一直点 (1659,766)，y 偏 224px —— 这就是点击落空的根因）
  · `BattleOfficiallyBegin` ROI `[1165,20,75,65]` → 中心 (1803, 78)@1920 = 战斗 HUD 的正式开始标志
  · `BattleQuickFormation` ROI `[816,0,404,149]` → 中心 (1527,111)@1920 = 快捷编队按钮
  · `EnterChooseLevelOfDifficulty` ROI `[0,598,131,122]` → 中心 (97,988)@1920
- `template/Battle/BattleFlag/`：`BattleCostFlag.png`、`BattleHpFlag.png`、`BattleKillsFlag.png`、
  `BattleOfficiallyBegin.png`、`BattleOpersFlag.png` —— 战斗 HUD 的各个标志物
- `template/StageNavigation/Episode/NN@EnterEpisodeNew.png` —— **每一章的章节图标**
  ⇒ 可以模板匹配直接定位"第 12 章"图标并点击，彻底解决"章节跑偏"
- `template/Battle/BattleFlag/BattleCostFlag.png` —— 费用标志，可用于**精确定位费用区域**（替代我猜的 ROI）

## 用法
    ma = MaaAnchor()
    hit = ma.match(frame, ma.EPISODE(12))          # 找第 12 章图标
    if hit: print(hit['center_frame'])             # → 1920×1080 下的点击点
    ma.click_point(hit)                            # 直接给注入层用
"""
from __future__ import annotations

import os

import cv2
import numpy as np

MAA_ROOT = r'D:\__soft\MAA\resource'
BASE_W, BASE_H = 1280, 720


class MaaAnchor:
    """MAA 模板 → 当前帧的锚点匹配器（帧自动缩放到 1280×720 的 MAA 基准空间）。"""

    # 常用锚点（相对 template/ 的路径）
    START_BUTTON_NORMAL = 'Battle/StartButton/BattleStartNormal.png'
    START_BUTTON_EXERCISE = 'Battle/StartButton/BattleStartExercise.png'   # 演习
    BATTLE_OFFICIAL_BEGIN = 'Battle/BattleFlag/BattleOfficiallyBegin.png'
    COST_FLAG = 'Battle/BattleFlag/BattleCostFlag.png'
    HP_FLAG = 'Battle/BattleFlag/BattleHpFlag.png'
    KILLS_FLAG = 'Battle/BattleFlag/BattleKillsFlag.png'
    OPERS_FLAG = 'Battle/BattleFlag/BattleOpersFlag.png'
    DROPS_TOUGH = 'Battle/StageDrops/StageDrops-Difficulty-Tough.png'

    # tasks.json 里验证过的 ROI（MAA 基准 1280×720：[x, y, w, h]）
    ROI_START_PRE = (1000, 600, 280, 120)      # 「开始行动/作战/突袭…」
    ROI_OFFICIAL_BEGIN = (1165, 20, 75, 65)
    ROI_QUICK_FORMATION = (816, 0, 404, 149)
    ROI_DIFFICULTY_CHOOSE = (0, 598, 131, 122)

    def __init__(self, root: str = MAA_ROOT, thr: float = 0.80):
        self.root = root
        self.thr = float(thr)
        self._cache: dict[str, np.ndarray] = {}

    # ---------- 模板 ----------
    @staticmethod
    def EPISODE(n: int) -> str:
        """第 n 章的章节图标模板（MAA 命名：NN@EnterEpisodeNew.png）。"""
        return f'StageNavigation/Episode/{int(n):02d}@EnterEpisodeNew.png'

    def template_path(self, rel: str) -> str:
        return os.path.join(self.root, 'template', rel.replace('/', os.sep))

    def load(self, rel: str):
        if rel in self._cache:
            return self._cache[rel]
        p = self.template_path(rel)
        img = cv2.imread(p, cv2.IMREAD_COLOR) if os.path.exists(p) else None
        self._cache[rel] = img
        return img

    # ---------- 匹配 ----------
    def match(self, frame, rel: str, roi=None, thr: float | None = None):
        """在 frame（任意分辨率、16:9）里找模板 `rel`。

        roi: MAA 基准坐标 (x, y, w, h)；None = 全图。
        返回 dict(score, center_base, center_frame, rect_frame, scale) 或 None。
        """
        tpl = self.load(rel)
        if tpl is None or frame is None:
            return None
        fh, fw = frame.shape[:2]
        scale = fw / float(BASE_W)
        small = cv2.resize(frame, (BASE_W, BASE_H), interpolation=cv2.INTER_AREA) \
            if (fw, fh) != (BASE_W, BASE_H) else frame
        if roi:
            x, y, w, h = [int(v) for v in roi]
            x0, y0 = max(0, x), max(0, y)
            x1, y1 = min(BASE_W, x + w), min(BASE_H, y + h)
            area = small[y0:y1, x0:x1]
            off = (x0, y0)
        else:
            area, off = small, (0, 0)
        th, tw = tpl.shape[:2]
        if area.shape[0] < th or area.shape[1] < tw:
            return None
        res = cv2.matchTemplate(area, tpl, cv2.TM_CCOEFF_NORMED)
        _, maxv, _, maxloc = cv2.minMaxLoc(res)
        if maxv < (self.thr if thr is None else thr):
            return None
        cx = off[0] + maxloc[0] + tw / 2.0
        cy = off[1] + maxloc[1] + th / 2.0
        return {
            'template': rel, 'score': float(maxv),
            'center_base': (cx, cy),
            'center_frame': (cx * scale, cy * scale),
            'rect_frame': ((off[0] + maxloc[0]) * scale, (off[1] + maxloc[1]) * scale,
                           tw * scale, th * scale),
            'scale': scale,
        }

    def click_point(self, hit) -> tuple[int, int] | None:
        """把命中结果换成**帧坐标**下的点击点（取整）。"""
        if not hit:
            return None
        x, y = hit['center_frame']
        return int(round(x)), int(round(y))

    def find_episode(self, frame, n: int, thr: float | None = None):
        """找第 n 章图标（全图匹配）。"""
        return self.match(frame, self.EPISODE(n), roi=None, thr=thr)

    def which_episode(self, frame, rng=range(1, 15), thr: float | None = None):
        """在给定章节范围内，返回命中最强的章节号与命中信息。"""
        best = None
        for n in rng:
            hit = self.find_episode(frame, n, thr=thr)
            if hit and (best is None or hit['score'] > best[1]['score']):
                best = (n, hit)
        return best
