# -*- coding: utf-8 -*-
"""patch_and_test_card.py — 给卡片识别器加"候选集限制"（编队内 11 人）并测试。"""
from __future__ import annotations

import io
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
VISION = r'C:\Users\23922\Documents\ds_harness\ak\code\vision'
sys.path.insert(0, VISION)
P = os.path.join(VISION, 'plugins', 'recognize', 'operator_card.py')

s = io.open(P, encoding='utf-8').read()

CAND = (
    "    def candidates_from_names(self, names) -> dict:\n"
    "        \"\"\"★把候选集限制到**编队内的若干干员**（如 11 人）——\n"
    "        比在 720 人里选可靠得多（实测 720 人时 top1−top2 边际仅 0.001~0.03，属噪声）。\"\"\"\n"
    "        ids = {}\n"
    "        for nm in names:\n"
    "            for cid in (self.mapping.get(nm) or []):\n"
    "                if cid in self.avatars:\n"
    "                    ids[cid] = self.avatars[cid]\n"
    "        return ids\n\n"
)
if 'candidates_from_names' not in s:
    s = s.replace("    def identify(self, img: np.ndarray, cx: int, y_band=CARD_Y) -> dict:",
                  CAND + "    def identify(self, img: np.ndarray, cx: int, y_band=CARD_Y, pool=None) -> dict:")
    s = s.replace("        for cid, av in self.avatars.items():",
                  "        for cid, av in (pool or self.avatars).items():")
    s = s.replace("    def identify_all(self, img: np.ndarray, y_band=CARD_Y) -> list[dict]:",
                  "    def identify_all(self, img: np.ndarray, y_band=CARD_Y, names=None) -> list[dict]:")
    s = s.replace("            r = self.identify(img, int(s['cx']), y_band)",
                  "            r = self.identify(img, int(s['cx']), y_band,\n"
                  "                              pool=self.candidates_from_names(names) if names else None)")
    io.open(P, 'w', encoding='utf-8').write(s)
    print('已加候选集限制')
else:
    print('已有候选集限制，跳过')

import cv2                                                            # noqa: E402
from plugins.recognize.operator_card import OperatorCardMatcher       # noqa: E402

SQUAD = ['卡缇', '安赛尔', '芬', '泡普卡', '安德切尔', '月见夜',
         '斑点', '香草', '玫兰莎', '克洛丝', '史都华德']
m = OperatorCardMatcher()
img = cv2.imread(r'C:\Users\23922\Documents\ds_harness\ak\.tmp\axisdep_D6.png')
print(f'编队候选 {len(m.candidates_from_names(SQUAD))} 个')
for r in m.identify_all(img, names=SQUAD):
    print(f"  cx={r['cx']:<5} → {r['name']:<5} score={r['score']:.3f} "
          f"margin={r['margin']:.3f} top3={r['topk'][:3]}")
