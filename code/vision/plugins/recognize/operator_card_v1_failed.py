# -*- coding: utf-8 -*-
"""operator_card.py — ★**用现成头像库识别待部署卡片**（借用 PRTS+/MAA 的识别工程，不自造）。

## 用户指示（2026-09-15）
> 「尝试借鉴 **prts+ 或 maa 已有的识别工程**，识别**干员名对应的头像文件库**，
>   这在 2 者 resource 中均可找到」

## 资源（已在 PRTS+ 中找到）
- `D:\\__soft\\ak\\prts+\\_internal\\resource\\operator_mapping.json`
  —— **927 条「干员名 → [char_id]」**，例：`"月见夜": ["char_283_midn"]`
- `D:\\__soft\\ak\\prts+\\_internal\\resource\\avatar\\<char_id>.png`
  —— **180×180 方形头像**（与战斗内卡片缩略图同规格）

## 做法（无需读费用数字）
1. 从 HUD 底部取出每张卡片（复用 `Deployer.find_cards`）；
2. 裁出**卡面**（默认 `cx±58, y 940..1060`），缩放到 180×180；
3. 与头像库做**归一化互相关**（灰度 + 轻微多尺度/多偏移搜索取最大）；
4. 取最高分者为该卡干员，并给出**边际**（top1 − top2）作为置信度。

⇒ 之后"按轴表部署"就能**按干员名选卡**，而不是猜费用或取第 1 张。

## 用法
```python
from plugins.recognize.operator_card import OperatorCardMatcher
m = OperatorCardMatcher()
print(m.identify_all(img))      # [{'name','char_id','score','margin'}, ...]（左→右）
```
"""
from __future__ import annotations

import glob
import json
import os

import cv2
import numpy as np

PRTS_RES = r'D:\__soft\ak\prts+\_internal\resource'
MAA_RES = r'D:\__soft\MAA\resource'
CARD_Y = (938, 1064)


class OperatorCardMatcher:
    def __init__(self, res_dir: str = PRTS_RES, size: int = 180, topk: int = 5):
        self.res_dir = res_dir
        self.size = int(size)
        self.topk = topk
        self.win_fracs = (0.45, 0.6, 0.8, 1.0)
        self.mapping = {}
        mp = os.path.join(res_dir, 'operator_mapping.json')
        if os.path.exists(mp):
            self.mapping = json.load(open(mp, encoding='utf-8'))
        self.avatars: dict[str, np.ndarray] = {}
        self._load_avatars()

    # ---------------- 资源 ----------------
    def _load_avatars(self):
        ad = os.path.join(self.res_dir, 'avatar')
        for cid in {c for v in self.mapping.values() for c in (v or [])}:
            p = os.path.join(ad, f'{cid}.png')
            if not os.path.exists(p):
                continue
            im = cv2.imread(p)
            if im is None:
                continue
            self.avatars[cid] = cv2.cvtColor(
                cv2.resize(im, (self.size, self.size), interpolation=cv2.INTER_AREA),
                cv2.COLOR_BGR2GRAY)

    def name_of(self, char_id: str) -> str:
        for nm, ids in self.mapping.items():
            if char_id in (ids or []):
                return nm
        return char_id

    # ---------------- 识别 ----------------
    def _prep(self, crop: np.ndarray, msz: int | None = None) -> np.ndarray:
        n = int(msz or self.size)
        g = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
        g = cv2.resize(g, (n, n), interpolation=cv2.INTER_AREA)
        g = cv2.equalizeHist(g)
        return g.astype(np.float32)

    @staticmethod
    def _zn(a: np.ndarray) -> np.ndarray:
        return (a - a.mean()) / (a.std() + 1e-6)

    def _best_over_windows(self, av: np.ndarray, q: np.ndarray) -> float:
        """★卡片是"脸部特写"、而头像库是"半身立绘" ⇒ 在立绘上**滑窗**找最相似区域。

        窗为正方形，边长取立绘的 45%~100%，位置在立绘上按网格滑动；
        每个窗口缩放到与卡片同尺寸后做零均值归一化互相关，取最大值。
        """
        n = av.shape[0]
        best = -1.0
        wins = self.win_fracs
        for f in wins:
            w = max(16, int(n * f))
            step = max(1, w // 3)
            for y in range(0, n - w + 1, step):
                for x in range(0, n - w + 1, step):
                    sub = av[y:y + w, x:x + w]
                    s = float((self._zn(self._prep(sub, q.shape[0])) * q).mean())
                    if s > best:
                        best = s
        return best

    def candidates_from_names(self, names) -> dict:
        """★把候选集限制到**编队内的若干干员**（如 11 人）——
        比在 720 人里选可靠得多（实测 720 人时 top1−top2 边际仅 0.001~0.03，属噪声）。"""
        ids = {}
        for nm in names:
            for cid in (self.mapping.get(nm) or []):
                if cid in self.avatars:
                    ids[cid] = self.avatars[cid]
        return ids

    def identify(self, img: np.ndarray, cx: int, y_band=CARD_Y, pool=None) -> dict:
        y0, y1 = y_band
        half = 58
        crop = img[y0:y1, max(0, cx - half):cx + half]
        if crop.size == 0:
            return {'name': None, 'char_id': None, 'score': 0.0, 'margin': 0.0}
        q = self._zn(self._prep(crop, 72))          # 卡片统一到 72 便于快速滑窗比对
        best = []
        for cid, av in (pool or self.avatars).items():
            best.append((self._best_over_windows(av, q), cid))
        best.sort(reverse=True)
        top = best[:self.topk]
        score = top[0][0]
        margin = score - (top[1][0] if len(top) > 1 else 0.0)
        return {'name': self.name_of(top[0][1]), 'char_id': top[0][1],
                'score': round(score, 4), 'margin': round(margin, 4),
                'topk': [(round(s, 4), self.name_of(c)) for s, c in top]}

    def identify_all(self, img: np.ndarray, y_band=CARD_Y, names=None) -> list[dict]:
        from plugins.action.deploy import Deployer
        segs = Deployer(None).find_cards(img=img, y_band=(y_band[0] - 63, y_band[1] + 11)) or []
        out = []
        for s in sorted(segs, key=lambda k: k['cx']):
            r = self.identify(img, int(s['cx']), y_band,
                              pool=self.candidates_from_names(names) if names else None)
            r['cx'] = int(s['cx'])
            out.append(r)
        return out


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))))          # 让 `plugins.*` 可导入
    TMP = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'
    files = sys.argv[1:] or ['axisdep_D4.png']
    m = OperatorCardMatcher()
    print(f'头像库 {len(m.avatars)} 张；映射 {len(m.mapping)} 条干员名')
    for fn in files:
        p = os.path.join(TMP, fn)
        if not os.path.exists(p):
            print('  缺样本', fn)
            continue
        img = cv2.imread(p)
        print(f'\n--- {fn} ---')
        for r in m.identify_all(img):
            print(f"  cx={r['cx']:<5} → {r['name']:<6} ({r['char_id']}) "
                  f"score={r['score']:.3f} margin={r['margin']:.3f}  "
                  f"top3={r['topk'][:3]}")
