# -*- coding: utf-8 -*-
"""operator_card.py — ★**待部署区头像识别**（按用户指引"直接读干员头像"，实测可用）。

## 为什么/依据
用户说明：「头像文件其实就是游戏本地读取、**显示到局内待部署区的图片**；
**排除头像透明区域和费用等干扰后应完全一致**」。
本项目已用实验证实：
- 在编队页卡面内**搜索"与头像完全一致的矩形"**得 **掩膜 NCC = 0.796**，目视确认为同一张画的同一构图；
- **编队页 11/11 = 100%**（真实卡片中心：行1 y=306、**行2 y≈740** —— 注意不是 819）；
- **战斗待部署区 8/10**（NCC 0.59~0.74、边际 0.16~0.48），
  且 2 处"未中"实为**同费用**（安赛尔/斑点 皆 15 费）的真值排序任意所致 ⇒ **实际约 10/10**；
  ⇒ **头像法是能解"同费用"歧义的主判据**（用户指出费用不足，正是指这一点）。

## 关键几何（本机 1920×1080 实测）
| 场景 | 卡片中心 | 头像区 |
|---|---|---|
| **战斗待部署区** | `x = 139 + pitch·(i+0.5)`，`pitch=(1959−139)/n`，`y=1007` | `x ± 85`、**`y 912..1078`（下缘被裁）** |
| 编队页行1 | `x=[234,468,693,918,1144,1369]`，`y=306` | 卡面内矩形 `(60,68,180,176)`（相对 260×460 卡框） |
| 编队页行2 | `x=[236,458,701,932,1170]`，**`y=740`** | 同上 |

## 用法
```python
m = OperatorCardMatcher()
row = m.identify_deploy_row(img, n_cards=10, candidates=['芬','月见夜',...])
# → [{'name','char_id','score','margin','cx'}, ...]（左→右）
```
"""
from __future__ import annotations

import json
import os

import cv2
import numpy as np

PRTS_RES = r'D:\__soft\ak\prts+\_internal\resource'
# 战斗待部署区几何（实测）
DEPLOY_X_LEFT, DEPLOY_X_RIGHT = 139.0, 1959.0
DEPLOY_Y = 1007
PORTRAIT_HALF = 85
PORTRAIT_Y = (912, 1078)
X_SEARCH = 48            # 每卡 x 局部搜索范围（吸收步距累积误差）
# 编队页几何（实测）
SQUAD_ROWS = [([234, 468, 693, 918, 1144, 1369], 306),
              ([236, 458, 701, 932, 1170], 740)]
SQUAD_CARD = (260, 460)
SQUAD_RECT = (60, 68, 180, 176)


def _ncc(patch_bgr, av_bgr, av_alpha) -> float:
    """仅在头像 `alpha>32` 的像素上做归一化互相关（**排除透明区**）。"""
    g1 = cv2.cvtColor(patch_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
    g2 = cv2.cvtColor(av_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
    m = av_alpha > 32
    if m.sum() < 200:
        return -1.0
    a, b = g1[m], g2[m]
    return float((((a - a.mean()) / (a.std() + 1e-6)) *
                  ((b - b.mean()) / (b.std() + 1e-6))).mean())


class OperatorCardMatcher:
    def __init__(self, res_dir: str = PRTS_RES, candidates=None):
        self.mapping = {}
        mp = os.path.join(res_dir, 'operator_mapping.json')
        if os.path.exists(mp):
            self.mapping = json.load(open(mp, encoding='utf-8'))
        self.av_dir = os.path.join(res_dir, 'avatar')
        self.lib: dict[str, tuple] = {}
        if candidates:
            self._ensure(candidates)
        else:
            for nm in list(self.mapping.keys()):
                self._ensure([nm])

    # ---------------- 资源 ----------------
    def _ensure(self, names):
        for nm in names:
            if nm in self.lib:
                continue
            for cid in (self.mapping.get(nm) or []):
                p = os.path.join(self.av_dir, f'{cid}.png')
                if not os.path.exists(p):
                    continue
                im = cv2.imread(p, cv2.IMREAD_UNCHANGED)
                if im is None:
                    continue
                bgr = im[:, :, :3]
                a = (im[:, :, 3] if im.shape[2] == 4
                     else np.full(im.shape[:2], 255, np.uint8))
                self.lib[nm] = (bgr, a)

    def name_of(self, char_id: str) -> str:
        for nm, ids in self.mapping.items():
            if char_id in (ids or []):
                return nm
        return char_id

    # ---------------- 通用：给定抠图 → 排名 ----------------
    def rank(self, patch_bgr, candidates=None) -> list[tuple]:
        if candidates:
            self._ensure(candidates)
        lib = {k: v for k, v in self.lib.items()
               if not candidates or k in set(candidates)}
        sc = []
        for nm, (b, a) in lib.items():
            p2 = cv2.resize(patch_bgr, (b.shape[1], b.shape[0]),
                            interpolation=cv2.INTER_AREA)
            sc.append((_ncc(p2, b, a), nm))
        sc.sort(reverse=True)
        return sc

    # ---------------- ★按名字直接定位卡片（自标定，不依赖 pitch/几何假设） ----------------
    def locate_operator_card(self, img, name: str, candidates=None,
                             y_band=(905, 1075), halves=(70, 80, 90, 100),
                             x_range=(100, 1900), step: int = 4) -> dict:
        """**在待部署区整行扫描目标干员自己的头像**，返回最佳位置。

        为什么不用 pitch 推算：11 张卡的实测几何与 10 张不同，且按"检测到的段"拟合易错位
        （实测 `芬` 在 11 张时中心 x=228/半宽90/NCC 0.611；而 pitch 拟合给出互相矛盾的 142/178）。
        ⇒ 直接**逐位置扫描**并用**判别性分数** `NCC(本人) − max NCC(他人)` 选峰，
        既能定位又天然排除"在错误的卡上匹配到别人"的情形。
        """
        if candidates:
            self._ensure(candidates)
        pool = {k: v for k, v in self.lib.items()
                if (not candidates or k in set(candidates)) and k != name}
        me = self.lib.get(name)
        if me is None:
            return {'ok': False, 'reason': f'无该干员头像: {name}'}
        y0, y1 = y_band
        best = (-9.0, None)
        for half in halves:
            for cx in range(x_range[0], x_range[1] + 1, step):
                patch = img[y0:y1, cx - half:cx + half]
                if patch.shape[0] < 60 or patch.shape[1] < 40:
                    continue
                p2 = cv2.resize(patch, (me[0].shape[1], me[0].shape[0]),
                                interpolation=cv2.INTER_AREA)
                s_me = _ncc(p2, me[0], me[1])
                s_other = max((_ncc(p2, b, a) for b, a in pool.values()), default=0.0)
                disc = s_me - s_other
                if disc > best[0]:
                    best = (disc, {'cx': cx, 'half': half, 'y0': y0,
                                   'ncc_me': round(s_me, 4),
                                   'ncc_other': round(s_other, 4)})
        if best[1] is None:
            return {'ok': False, 'reason': '扫描未获得候选'}
        return {'ok': True, **best[1], 'discriminative': round(best[0], 4)}

    # ---------------- 战斗待部署区 ----------------
    @staticmethod
    def detect_card_columns(img, y_band=(950, 1075), thr_ratio=0.62,
                            min_w=60, max_w=260):
        """★**自动检测待部署区卡片的列**（自标定，不依赖写死的 pitch）。

        原理：卡片头像是**亮矩形**、卡与卡之间是**暗缝** ⇒ 在头像带内取列均值，
        以 `thr = 均值×比例` 阈值分段，保留宽度合理的段，返回其中心与宽度。
        ⇒ 卡片数从 9~12 变化时几何**自动适配**（此前写死 pitch 导致 11 张时错位）。
        """
        y0, y1 = y_band
        band = img[y0:y1]
        g = cv2.cvtColor(band, cv2.COLOR_BGR2GRAY).astype(np.float32)
        col = g.mean(axis=0)
        thr = max(20.0, float(col.mean()) * thr_ratio)
        mask = col > thr
        segs, s = [], None
        for i, m in enumerate(mask):
            if m and s is None:
                s = i
            elif not m and s is not None:
                if min_w <= i - s <= max_w:
                    segs.append((s, i))
                s = None
        if s is not None and min_w <= len(mask) - s <= max_w:
            segs.append((s, len(mask)))
        out = [{'cx': (a + b) // 2, 'w': b - a, 'x0': a, 'x1': b} for a, b in segs]
        return out

    def identify_deploy_row(self, img, n_cards: int | None = None, candidates=None,
                            x_search: int = X_SEARCH, step: int = 4,
                            auto_columns: bool = True) -> list[dict]:
        """战斗待部署区识别。

        `auto_columns=True`（默认）时**用 `detect_card_columns` 自动取列**（推荐，自适配卡数）；
        否则按 `n_cards` 用 `X_LEFT/pitch` 推算（保留作对照）。
        """
        if candidates:
            self._ensure(candidates)
        lib = {k: v for k, v in self.lib.items()
               if not candidates or k in set(candidates)}
        y0, y1 = PORTRAIT_Y
        cols = None
        if auto_columns:
            cols = self.detect_card_columns(img)
            if n_cards and abs(len(cols) - n_cards) > 1:
                cols = None                     # 检测结果与预期差太多 ⇒ 退回几何推算
        if cols:
            centers = [(c['cx'], max(40, int(c['w'] * 0.5))) for c in cols]
        else:
            n = n_cards or 10
            pitch = (DEPLOY_X_RIGHT - DEPLOY_X_LEFT) / max(1, n)
            half = max(40, int(round(pitch * 0.47)))
            centers = [(int(DEPLOY_X_LEFT + pitch * (i + 0.5)), half) for i in range(n)]
        out = []
        for (cx0, half) in centers:
            best = (-9.0, None, 0)
            for dcx in range(-x_search, x_search + 1, step):
                cxi = cx0 + dcx
                patch = img[y0:y1, max(0, cxi - half):cxi + half]
                if patch.shape[0] < 40 or patch.shape[1] < 40:
                    continue
                sc = []
                for nm, (b, a) in lib.items():
                    p2 = cv2.resize(patch, (b.shape[1], b.shape[0]),
                                    interpolation=cv2.INTER_AREA)
                    sc.append((_ncc(p2, b, a), nm))
                sc.sort(reverse=True)
                if sc[0][0] > best[0]:
                    best = (sc[0][0], sc, cxi)
            if best[1] is None:
                out.append({'name': None, 'score': 0.0, 'margin': 0.0, 'cx': None})
                continue
            sc = best[1]
            out.append({'name': sc[0][1], 'score': round(sc[0][0], 4),
                        'margin': round(sc[0][0] - sc[1][0], 4), 'cx': best[2],
                        'half': half, 'top3': [n for _, n in sc[:3]]})
        return out

    # ---------------- 编队页 ----------------
    def identify_squad_grid(self, img, candidates=None, search: int = 20,
                            step: int = 4) -> list[dict]:
        """编队页两行卡片：**逐卡对齐搜索**后再比头像（缺了搜索会掉到 9/11）。"""
        if candidates:
            self._ensure(candidates)
        lib = {k: v for k, v in self.lib.items()
               if not candidates or k in set(candidates)}
        cw, ch = SQUAD_CARD
        rx, ry, rw, rh = SQUAD_RECT
        out = []
        for xs, y in SQUAD_ROWS:
            for cx in xs:
                x0, y0 = cx - cw // 2, y - ch // 2
                best = (-9.0, None)
                for dy in range(-search, search + 1, step):
                    for dx in range(-search, search + 1, step):
                        patch = img[y0 + ry + dy:y0 + ry + dy + rh,
                                    x0 + rx + dx:x0 + rx + dx + rw]
                        if patch.shape[0] < 40 or patch.shape[1] < 40:
                            continue
                        sc = []
                        for nm, (b, a) in lib.items():
                            p2 = cv2.resize(patch, (b.shape[1], b.shape[0]),
                                            interpolation=cv2.INTER_AREA)
                            sc.append((_ncc(p2, b, a), nm))
                        sc.sort(reverse=True)
                        if sc[0][0] > best[0]:
                            best = (sc[0][0], sc)
                if best[1] is None:
                    continue
                sc = best[1]
                out.append({'name': sc[0][1], 'score': round(sc[0][0], 4),
                            'margin': round(sc[0][0] - sc[1][0], 4), 'cx': cx,
                            'top3': [n for _, n in sc[:3]]})
        return out


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    TMP = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'
    SQUAD = ['卡缇', '安赛尔', '芬', '泡普卡', '安德切尔', '月见夜',
             '斑点', '香草', '玫兰莎', '克洛丝', '史都华德']
    m = OperatorCardMatcher(candidates=SQUAD)
    print(f'候选 {len(m.lib)} 人')
    img = cv2.imread(os.path.join(TMP, 'live_03_squad.png'))
    hits = 0
    for k, r in enumerate(m.identify_squad_grid(img)):
        ok = r['name'] == SQUAD[k]
        hits += ok
        print(f"  编队#{k} {SQUAD[k]:<6} → {r['name']:<6} {r['score']:.3f} "
              f"边际{r['margin']:.3f} {'✅' if ok else '✗'}")
    print(f'编队页命中 {hits}/11')
    img2 = cv2.imread(os.path.join(TMP, 'axisdep_D6.png'))
    EXPECT = ['克洛丝', '安德切尔', '香草', '玫兰莎', '月见夜', '安赛尔',
              '斑点', '卡缇', '史都华德', '泡普卡']
    print('\n战斗待部署区：')
    for k, r in enumerate(m.identify_deploy_row(img2, 10, candidates=SQUAD)):
        print(f"  卡#{k} 真值(费用序){EXPECT[k]:<6} → {r['name']:<6} "
              f"{r['score']:.3f} 边际{r['margin']:.3f} x={r['cx']}")
