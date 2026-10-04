# -*- coding: utf-8 -*-
"""card_index.py — ★由"费用升序"推算**卡片序号**（无需图像识别）。

## 依据（已用实机验证）
1. 战斗卡片行**按费用升序**；
2. 干员费用 = `get_operator(cid, elite, level, potential)['attrs']['cost'] − 天赋/潜能减免`；
   实测：1-1 编队 11 人费用升序 = **[8,9,9,9,13,14,15,15,16,16,17]**，
   而 `axisdep_D6.png`（芬已部署）实机卡片费用 = **[9,9,9,13,14,15,15,16,16,17]** ⇒ **逐项一致**；
3. **已部署干员的卡片会从行内移除** ⇒ 序号须在"**未部署的**编队成员"里按费用升序计算。

## 用法
```python
plan = CardPlan(SQUAD)                 # SQUAD = [(名字, char_id), ...]
plan.mark_deployed('芬')
idx = plan.index_of('月见夜')          # → 在剩余卡片中的位次（0 基）
```
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from ak_sim import data as D          # noqa: E402

# 编队（1-1 标定对局）；天赋费用减免按干员配置
DEFAULT_SQUAD = [('卡缇', 'char_209_ardign'), ('安赛尔', 'char_212_ansel'),
                 ('芬', 'char_123_fang'), ('泡普卡', 'char_281_popka'),
                 ('安德切尔', 'char_211_adnach'), ('月见夜', 'char_283_midn'),
                 ('斑点', 'char_284_spot'), ('香草', 'char_240_wyvern'),
                 ('玫兰莎', 'char_208_melan'), ('克洛丝', 'char_124_kroos'),
                 ('史都华德', 'char_210_stward')]
DEFAULT_TALENT_COST = {'芬': 1}          # 「轻量化」−1


class CardPlan:
    def __init__(self, squad=None, talent_cost=None, elite=1, level=55, potential=6):
        self.squad = list(squad or DEFAULT_SQUAD)
        self.talent = dict(talent_cost or DEFAULT_TALENT_COST)
        self.costs = {}
        for nm, cid in self.squad:
            try:
                base = int(round(float(D.get_operator(
                    cid, elite=elite, level=level, potential=potential,
                    trust=200)['attrs']['cost'])))
            except Exception:                                    # noqa: BLE001
                continue
            self.costs[nm] = base - self.talent.get(nm, 0)
        self.deployed: set[str] = set()

    # ---------------- 查询 ----------------
    def remaining(self) -> list[tuple[int, str]]:
        """未部署成员的 (费用, 名字)，按**费用升序**（同费用按名字稳定排序）。"""
        return sorted((c, nm) for nm, c in self.costs.items() if nm not in self.deployed)

    def index_of(self, name: str) -> int | None:
        """目标干员在**当前卡片行**中的 0 基序号。"""
        rest = self.remaining()
        for i, (_, nm) in enumerate(rest):
            if nm == name:
                return i
        return None

    def expected_row(self) -> list:
        return [c for c, _ in self.remaining()]

    def mark_deployed(self, name: str) -> None:
        self.deployed.add(name)

    def reset(self) -> None:
        self.deployed.clear()


def export(path: str | None = None, **kw) -> str:
    """把"费用表 + 序号规则"导出为 JSON，供**打图侧**（不同 venv）读取，避免跨环境导入。"""
    import json
    p = CardPlan(**kw)
    data = {
        '_doc': '卡片序号推算表（结构性方案，无需图像识别）：卡片行按费用升序，'
                '已部署干员的卡片会从行内移除。生成者 ak/sim/draft/card_index.py',
        'squad': {nm: c for nm, c in p.costs.items()},
        'order': [nm for _, nm in p.remaining()],
        'costs_sorted': p.expected_row(),
        'talent_cost': p.talent,
    }
    out = path or os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(HERE))),
        'ak', 'data', 'derived', 'card_plan.json')
    out = os.path.normpath(out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    return out


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    if '--export' in sys.argv:
        out = export()
        print('已导出:', out)
    p = CardPlan()
    print('编队费用（升序）:', p.expected_row())
    print('  芬 → 序号', p.index_of('芬'), ' 月见夜 → 序号', p.index_of('月见夜'))
    p.mark_deployed('芬')
    print('芬部署后：', p.expected_row())
    print('  月见夜 → 序号', p.index_of('月见夜'),
          '（应与实机 axisdep_D6.png 的 14 费卡位次一致：第 5 张 = 下标 4）')
